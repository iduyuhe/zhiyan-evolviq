"""多 Agent 编排器（Orchestrator）——并行执行多 Agent 并生成综合报告。

职责：
1. 接收 OrchestratorPlan，并行调用各 Agent（`asyncio.gather`）。
2. 收集各 Agent 的结果 + 应用授权边界（复用 authorization.evaluate_batch）。
3. 跨 Agent 聚合：
   - 关键数字汇总（如 OEE、齐套率、能耗等）
   - 跨 Agent 共同发现（如 supply_chain 报缺料 + aps_scheduler 报延期 → 强相关）
   - 优先级行动清单（按风险/影响排序）
4. 韧性降级：单个 Agent 失败不影响整体，错误计入 aggregated_result["errors"]。

调用链：
    OrchestratorPlan
        │
        ▼
    MultiAgentOrchestrator.execute_plan(plan)
        │   并行执行每个 SubTask
        │   ↓
        │   list[AgentExecutionResult]   (含 result / autonomous / pending / error)
        ▼
    MultiAgentOrchestrator.aggregate(plan, executions)
        │
        ▼
    MultiAgentReport (dict)
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

from src.runtime.agent.goal_decomposer import OrchestratorPlan, SubTask

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据契约
# ---------------------------------------------------------------------------


@dataclass
class AgentExecutionResult:
    """单个 Agent 一次调用的完整执行结果"""
    task_id: str
    agent: str
    sub_goal: str
    focus: str
    status: str = "pending"            # pending / running / completed / failed
    started_at: float = 0.0
    finished_at: float = 0.0
    result: dict | None = None         # Agent.analyze() 的原始结果
    autonomous_actions: list[dict] = field(default_factory=list)
    pending_interventions: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_ms(self) -> int:
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at) * 1000)
        return 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_ms"] = self.duration_ms
        return d


@dataclass
class MultiAgentReport:
    """多 Agent 协作综合报告（返回给前端 / API）"""
    orchestration_id: str
    goal: str
    strategy: str
    source: str                        # rule / llm / template
    rationale: str
    sub_task_count: int
    success_count: int
    failed_count: int
    total_duration_ms: int
    started_at: float
    finished_at: float
    executions: list[dict]             # 每个 AgentExecutionResult.to_dict()
    summary: str                       # 跨 Agent 总体摘要（确定性）
    cross_findings: list[str]          # 跨 Agent 共同发现（确定性规则抽取）
    priority_actions: list[dict]       # 优先级行动清单
    key_metrics: dict[str, Any]        # 关键数字（OEE/齐套率/能耗等）
    errors: list[dict]                 # 失败子任务清单

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 编排器
# ---------------------------------------------------------------------------


class MultiAgentOrchestrator:
    """多 Agent 编排器——并行执行 + 跨 Agent 汇总。

    设计原则：
    1. **单 Agent 失败不阻断整体**：`asyncio.gather(return_exceptions=True)`。
    2. **授权边界沿用**：复用 authorization.evaluate_batch 评估 actions_taken。
    3. **韧性降级**：每个 Agent 内部已有降级（PG→SQLite/Neo4j→内存/网关→simulated），
       编排器层面再加一层——LLM/外网不可用时仍可执行。
    """

    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id

    # -----------------------------------------------------------------------
    # 入口
    # -----------------------------------------------------------------------

    async def run(self, plan: OrchestratorPlan) -> MultiAgentReport:
        """一站式：执行计划 + 汇总报告"""
        executions = await self.execute_plan(plan)
        report = self.aggregate(plan, executions)
        return report

    # -----------------------------------------------------------------------
    # 执行层
    # -----------------------------------------------------------------------

    async def execute_plan(self, plan: OrchestratorPlan) -> list[AgentExecutionResult]:
        """并行执行所有子任务。

        简单 DAG：当前 MVP 只处理「depends_on 全空」与「depends_on 全在前一批」的二层场景；
        更复杂 DAG 留给 v2（拓扑排序）。
        """
        # 按层分组：第 0 层 = 无依赖；第 1 层 = 依赖第 0 层；...
        layers = self._topo_sort(plan.sub_tasks)
        all_executions: list[AgentExecutionResult] = []

        for layer in layers:
            # 同层并行
            tasks = [self._execute_one(st) for st in layer]
            layer_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in layer_results:
                if isinstance(r, Exception):
                    # 不应发生（_execute_one 已捕获），兜底
                    logger.error(f"[Orchestrator] Unexpected layer exception: {r}")
                    all_executions.append(AgentExecutionResult(
                        task_id="unknown", agent="unknown", sub_goal="", focus="",
                        status="failed", error=str(r),
                    ))
                else:
                    all_executions.append(r)

        return all_executions

    async def _execute_one(self, sub_task: SubTask) -> AgentExecutionResult:
        """执行单个子任务：调用 Agent + 评估授权边界。"""
        from src.runtime.agent.router import execute_by_agent
        from src.runtime.core.authorization import authorization
        from src.runtime.core.intervention import intervention_queue, Intervention
        from src.runtime.core.metrics import metrics
        from src.runtime.models.authorization import PlannedAction
        from src.meta_agent.audit import audit_logger

        exec_result = AgentExecutionResult(
            task_id=sub_task.task_id,
            agent=sub_task.agent,
            sub_goal=sub_task.sub_goal,
            focus=sub_task.focus,
            status="running",
            started_at=time.time(),
        )
        session_id = f"orch-{uuid.uuid4().hex[:8]}"

        try:
            # 1) Agent 分析
            agent_result = await execute_by_agent(sub_task.agent, sub_task.sub_goal)
            exec_result.result = agent_result

            # 2) 授权边界评估（与单 Agent 流程一致）
            boundary = authorization.for_tenant(self.tenant_id).get_for_agent(sub_task.agent)
            actions: list[PlannedAction] = []
            for act in (agent_result.get("actions_taken") or []):
                actions.append(PlannedAction(
                    type=act.get("type", "unknown"),
                    category=act.get("category") or act.get("line_id") or act.get("target") or "",
                    qty=int(act.get("qty", 0)),
                    confidence=float(act.get("confidence", 1.0)),
                    price_delta_pct=float(act.get("price_delta_pct", 0.0)),
                    detail=act.get("detail", ""),
                    session_id=session_id,
                ))
            if boundary and actions:
                decisions = authorization.for_tenant(self.tenant_id).evaluate_batch(boundary, actions)
                for dec in decisions:
                    if dec.decision == "auto":
                        exec_result.autonomous_actions.append({
                            "type": dec.action.type,
                            "detail": dec.action.detail,
                            "status": "auto_executed",
                        })
                    else:
                        ivt = Intervention(
                            session_id=session_id,
                            agent=sub_task.agent,
                            action=dec.action,
                            reason=dec.reason,
                            boundary_id=boundary.id,
                        )
                        intervention_queue.push(ivt)
                        exec_result.pending_interventions.append(ivt.to_dict())
                        event_bus_publish(sub_task.agent, dec)
                metrics.record(
                    session_id=session_id,
                    agent=sub_task.agent,
                    total=len(decisions),
                    auto=len(exec_result.autonomous_actions),
                    human=len(exec_result.pending_interventions),
                )

            exec_result.status = "completed"
            audit_logger.log(session_id, "agent_executed", sub_task.agent, {
                "sub_goal": sub_task.sub_goal[:120],
                "task_id": sub_task.task_id,
            }, tenant_id=self.tenant_id)

        except Exception as e:
            logger.exception(f"[Orchestrator] sub_task {sub_task.task_id} ({sub_task.agent}) failed: {e}")
            exec_result.status = "failed"
            exec_result.error = str(e)
            try:
                audit_logger.log(session_id, "agent_failed", sub_task.agent, {
                    "error": str(e)[:200],
                    "task_id": sub_task.task_id,
                }, tenant_id=self.tenant_id)
            except Exception:
                pass

        finally:
            exec_result.finished_at = time.time()

        return exec_result

    @staticmethod
    def _topo_sort(sub_tasks: list[SubTask]) -> list[list[SubTask]]:
        """简单拓扑排序：返回分层列表。空依赖的子任务在第 0 层。

        兜底：若检测到环/未知依赖，则把所有任务平铺到第 0 层（保证可执行）。
        """
        id_to_task = {t.task_id: t for t in sub_tasks}
        layers: list[list[SubTask]] = []
        placed: set[str] = set()

        # 第 0 层：无依赖
        layer0 = [t for t in sub_tasks if not t.depends_on]
        layers.append(layer0)
        placed.update(t.task_id for t in layer0)

        # 后续层：依赖项全部已 placed
        while True:
            nxt = [t for t in sub_tasks
                   if t.task_id not in placed
                   and all(d in placed for d in t.depends_on)]
            if not nxt:
                # 没有可推进的：要么完成（placed == all），要么有环（剩余非空 → 平铺兜底）
                remaining = [t for t in sub_tasks if t.task_id not in placed]
                if remaining:
                    logger.warning(f"[Orchestrator] cycle detected, flattening: {[t.task_id for t in remaining]}")
                    layers.append(remaining)
                break
            layers.append(nxt)
            placed.update(t.task_id for t in nxt)

        return layers

    # -----------------------------------------------------------------------
    # 汇总层
    # -----------------------------------------------------------------------

    def aggregate(
        self,
        plan: OrchestratorPlan,
        executions: list[AgentExecutionResult],
    ) -> MultiAgentReport:
        """跨 Agent 汇总：抽取共同发现、优先级、关键数字。"""
        started = min((e.started_at for e in executions if e.started_at), default=time.time())
        finished = max((e.finished_at for e in executions if e.finished_at), default=time.time())
        success = [e for e in executions if e.status == "completed"]
        failed = [e for e in executions if e.status == "failed"]

        # 关键数字抽取（按 Agent 类型挑标志性字段）
        key_metrics: dict[str, Any] = {}
        for e in success:
            r = e.result or {}
            ag = e.agent
            if ag == "supply_chain":
                if "completeness_pct" in r:
                    key_metrics.setdefault("completeness_pct", r["completeness_pct"])
            elif ag == "oee_optimizer":
                lines = r.get("lines") or []
                if lines:
                    avg_oee = sum(l.get("oee", 0) for l in lines) / len(lines)
                    key_metrics.setdefault("avg_oee", round(avg_oee, 1))
            elif ag == "yield_analysis":
                if "current_yield" in r:
                    key_metrics.setdefault("current_yield", r["current_yield"])
            elif ag == "energy_carbon":
                lines = r.get("lines") or []
                if lines:
                    total_kwh = sum(l.get("energy_kwh", 0) for l in lines)
                    total_carbon = sum(l.get("carbon_t", 0) for l in lines)
                    key_metrics.setdefault("total_energy_kwh", total_kwh)
                    key_metrics.setdefault("total_carbon_t", round(total_carbon, 2))
            elif ag == "wms_logistics":
                if "stock_health" in r:
                    key_metrics.setdefault("stock_health", r["stock_health"])
            elif ag == "cost_analysis":
                if "unit_cost" in r:
                    key_metrics.setdefault("unit_cost", r["unit_cost"])

        # 跨 Agent 共同发现（规则抽取）
        cross_findings = self._extract_cross_findings(executions)

        # 优先级行动清单：合并所有 pending_interventions + 关键 recommendations
        priority_actions: list[dict] = []
        for e in success:
            for p in e.pending_interventions:
                act = p.get("action", {})
                if isinstance(act, dict):
                    priority_actions.append({
                        "source_agent": e.agent,
                        "task_id": e.task_id,
                        "type": "intervention",
                        "detail": act.get("detail", ""),
                        "reason": p.get("reason", ""),
                        "boundary_id": p.get("boundary_id", ""),
                    })
            for rec in (e.result or {}).get("recommendations", [])[:3]:
                priority_actions.append({
                    "source_agent": e.agent,
                    "task_id": e.task_id,
                    "type": "recommendation",
                    "detail": rec,
                })

        # 按"待审批 > 关键建议"粗排序（保持原顺序即可——Agent 内部已按重要性排过）
        priority_actions = priority_actions[:20]   # 防止过长

        # 摘要
        summary = self._build_summary(plan, executions, key_metrics)

        return MultiAgentReport(
            orchestration_id=uuid.uuid4().hex,
            goal=plan.goal,
            strategy=plan.strategy,
            source=plan.source,
            rationale=plan.rationale,
            sub_task_count=len(plan.sub_tasks),
            success_count=len(success),
            failed_count=len(failed),
            total_duration_ms=int((finished - started) * 1000),
            started_at=started,
            finished_at=finished,
            executions=[e.to_dict() for e in executions],
            summary=summary,
            cross_findings=cross_findings,
            priority_actions=priority_actions,
            key_metrics=key_metrics,
            errors=[
                {"task_id": e.task_id, "agent": e.agent, "error": e.error}
                for e in failed
            ],
        )

    # -----------------------------------------------------------------------
    # 跨 Agent 洞察（规则化抽取——LLM 增强留给 v2）
    # -----------------------------------------------------------------------

    def _extract_cross_findings(self, executions: list[AgentExecutionResult]) -> list[str]:
        """跨 Agent 共同发现。规则化抽取：识别同时被多个 Agent 提到的主题。"""
        findings: list[str] = []
        success = [e for e in executions if e.status == "completed" and e.result]
        agents = {e.agent for e in success}

        # 模式 1：物料 + 排程 同时告急 → 缺料导致延期
        if "supply_chain" in agents and ("aps_scheduler" in agents or "demand_order" in agents):
            sc = next((e for e in success if e.agent == "supply_chain"), None)
            if sc and (sc.result.get("warning") or sc.result.get("alerts")):
                findings.append(
                    "供应链告警与排程/订单风险叠加：缺料可能直接传导到交期承诺，"
                    "建议优先处理齐套率最差的关键物料。"
                )

        # 模式 2：OEE + 维护 同时异常 → 设备健康拖累产线
        if "oee_optimizer" in agents and "pm_maintenance" in agents:
            oee = next((e for e in success if e.agent == "oee_optimizer"), None)
            if oee:
                avg = sum(l.get("oee", 100) for l in (oee.result.get("lines") or [])) / max(1, len(oee.result.get("lines") or []))
                if avg < 75:
                    findings.append(
                        f"OEE 平均 {avg:.1f}% 偏低，结合设备健康诊断，"
                        "建议先排查高停机损失设备，再优化性能率。"
                    )

        # 模式 3：质量 + 合规 双重风险 → 触发客户通知/召回评估
        if "quality_trace" in agents and "compliance_q" in agents:
            qt = next((e for e in success if e.agent == "quality_trace"), None)
            if qt and qt.result.get("root_cause"):
                findings.append(
                    f"质量追溯定位到根因（{qt.result['root_cause']}），"
                    "建议联动合规 Agent 评估是否触发客户通知或召回义务。"
                )

        # 模式 4：能耗 + OEE 联动 → 空载时段节能机会
        if "energy_carbon" in agents and "oee_optimizer" in agents:
            findings.append(
                "能耗与 OEE 联合视角下，可识别非生产时段空载能耗，"
                "联动排程做'关停-开机'优化有较大节能空间。"
            )

        # 模式 5：单 Agent 失败不阻断（韧性降级）
        failed = [e for e in executions if e.status == "failed"]
        if failed and len(success) > 0:
            findings.append(
                f"本次编排有 {len(failed)} 个 Agent 调用失败（{', '.join(e.agent for e in failed)}），"
                f"其余 {len(success)} 个 Agent 已完成；失败原因详见 errors。"
                "系统未中断，符合韧性降级原则。"
            )

        # 模式 6：所有 Agent 全部告警 → 紧急态
        warning_counts = sum(1 for e in success if e.result.get("warning") or e.result.get("alerts"))
        if warning_counts >= len(success) * 0.6 and len(success) > 1:
            findings.append(
                f"{warning_counts}/{len(success)} 个 Agent 都触发了告警，"
                "建议立即升级到管理驾驶舱，触发跨部门复盘。"
            )

        return findings

    def _build_summary(
        self,
        plan: OrchestratorPlan,
        executions: list[AgentExecutionResult],
        key_metrics: dict,
    ) -> str:
        """构建确定性摘要（不依赖 LLM）。"""
        success = [e for e in executions if e.status == "completed"]
        failed = [e for e in executions if e.status == "failed"]
        agent_names = "、".join(e.agent for e in success)

        parts = [f"已协同 {len(success)} 个 Agent"]
        if failed:
            parts.append(f"（{len(failed)} 个失败：{', '.join(e.agent for e in failed)}）")
        parts.append(f"完成对「{plan.goal[:30]}」的多视角分析。")
        parts.append(f"参与 Agent：{agent_names}。")

        if key_metrics:
            metrics_str = " / ".join(f"{k}={v}" for k, v in key_metrics.items())
            parts.append(f"关键指标：{metrics_str}。")

        pending_total = sum(len(e.pending_interventions) for e in success)
        if pending_total:
            parts.append(f"共 {pending_total} 个动作待人工审批（详见 priority_actions）。")
        return "".join(parts)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def event_bus_publish(agent: str, decision) -> None:  # 避免循环 import
    """延迟导入事件总线，避免循环依赖。"""
    try:
        from src.runtime.core.events import event_bus
        event_bus.publish(
            "intervention_required",
            "待人工审批",
            f"[{agent}] {decision.action.detail} — {decision.reason}",
            level="warning",
            source="orchestrator",
        )
    except Exception:
        pass
