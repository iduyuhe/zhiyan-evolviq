"""AgentEngine——AI原生核心编排层

职责：
1. 接收自然语言目标 → 分发给供应链Agent规划
2. 管理规划预览/确认/执行/介入的生命周期
3. Agent仅做"规划"，执行控制由Runtime管理
"""

import asyncio
import json
import logging

from src.runtime.core.events import event_bus
from src.runtime import persistence

logger = logging.getLogger(__name__)


class AgentEngine:
    """Agent执行引擎——管理Agent从规划到完成的全生命周期"""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    async def plan(self, session_id: str, goal: str, auth_boundary_id: str | None = None, tenant_id: str = "default") -> str:
        """
        接收自然语言目标 → 让Agent生成规划路径

        Args:
            session_id: 会话ID
            goal: 自然语言描述的目标
            auth_boundary_id: 授权边界配置ID（可选）
            tenant_id: 所属租户（多租户隔离用，默认 default）

        Returns:
            plan: Agent生成的规划（Markdown格式，展示给人确认）
        """
        # Step 1: 保存会话上下文
        self._sessions[session_id] = {
            "goal": goal,
            "auth_boundary_id": auth_boundary_id,
            "tenant_id": tenant_id,
            "status": "planning",
            "plan": None,
        }

        # 落库：AgentSession（planning）
        await persistence.save_session(
            session_id, goal, status="planning", auth_boundary_id=auth_boundary_id,
            tenant_id=tenant_id,
        )

        # 审计：目标设定
        from src.meta_agent.audit import audit_logger
        audit_logger.log(session_id, "goal_set", "human", {"goal": goal[:200]}, tenant_id=tenant_id)

        # Step 2: 路由到合适的Agent生成规划
        from src.runtime.agent.router import route_goal
        agent_name = route_goal(goal)
        self._sessions[session_id]["agent"] = agent_name

        if agent_name == "supply_chain":
            from src.agents.supply_chain.agent import supply_chain_agent
            plan_text = await supply_chain_agent.analyze_goal(goal, auth_boundary_id)
        elif agent_name == "pm_maintenance":
            from src.agents.pm_maintenance.agent import pm_agent
            result = await pm_agent.analyze(goal)
            # 对于非供应链Agent，将结果作为规划展示
            equip_summary = "\n".join([f"- {e['name']}: 健康评分 {e['health_score']}" for e in result.get("equipments", [])])
            plan_text = f"""## 📋 设备维护Agent诊断报告

### 目标理解
> {goal}

### 诊断结果
{equip_summary}

### 预警信息
{chr(10).join([f'- {a}' for a in result.get("alerts", [])]) or '- 无异常'}

### 建议操作
1. 查看详细设备健康报告
2. 安排高风险部件的预防维护
3. 跟踪维修建议的执行
"""
        elif agent_name == "yield_analysis":
            from src.agents.yield_analysis.agent import yield_agent
            result = await yield_agent.analyze(goal)
            defects = "\n".join([f"- {d['type']}: {d['ratio']}% ({d['trend']})" for d in result.get("defects", [])])
            plan_text = f"""## 📋 良率分析Agent诊断报告

### 目标理解
> {goal}

### 当前良率
**{result.get('current_yield', 'N/A')}%** (目标: {result.get('target_yield', 'N/A')}%)

### 缺陷分布
{defects}

### 发现
{chr(10).join([f'- {f}' for f in result.get('findings', [])])}

### 改进建议
{chr(10).join([f'- {r}' for r in result.get('recommendations', [])])}
"""
        elif agent_name == "quality_trace":
            from src.agents.quality_trace.agent import quality_trace_agent
            trace_result = await quality_trace_agent.trace(goal)
            trace_path_lines = []
            for step in trace_result.get("trace_path", []):
                trace_path_lines.append(f"  {step['step']}. {step['from']} -> {step['to']}: {step['finding']}")
            trace_path = "\n".join(trace_path_lines)

            equip_lines = []
            for eq in trace_result.get("suspected_equipments", []):
                equip_lines.append(f"  - {eq['name']}: match {eq['match_score']} ({eq['reason']})")
            equipments = "\n".join(equip_lines)
            plan_text = f"""## quality trace Agent report

### Goal
> {goal}

### Trace path
{trace_path}

### Suspected equipments
{equipments}

### Root cause
{trace_result.get('root_cause', 'analyzing')}

### Fix actions
{chr(10).join([f'- {a}' for a in trace_result.get('fix_actions', ['pending'])])}

### Similar historical cases
{trace_result.get('historical_similar', 0)} cases
"""
        elif agent_name in ("dfm_check", "bom_selector", "oee_optimizer", "eco_change", "smt_changeover", "aoi_judge", "ipc_standard", "aps_scheduler", "energy_carbon", "cost_analysis", "demand_order", "wms_logistics"):
            plan_text = await self._plan_for_generic_agent(agent_name, goal)
        else:
            plan_text = f"## 目标理解\n> {goal}\n\n无法识别合适的Agent，请明确目标场景。"

        # Step 2.5: AI原生 L2 推理层 —— 用 LLM 把确定性分析结果改写成自然语言规划
        # 规则原生 plan_text 始终作为兜底：LLM 不可用/超时/解析失败时不覆盖，绝不破坏管道
        from src.common.llm_client import llm_client
        if llm_client.available:
            llm_plan = await llm_client.generate_plan(agent_name, goal, plan_text)
            if llm_plan:
                plan_text = llm_plan
                self._sessions[session_id]["plan_source"] = "llm"
            else:
                self._sessions[session_id]["plan_source"] = "rule"
        else:
            self._sessions[session_id]["plan_source"] = "rule"

        # Step 3: 保存规划并返回
        self._sessions[session_id]["plan"] = plan_text
        self._sessions[session_id]["status"] = "awaiting_approval"
        # 落库：AgentSession（awaiting_approval + plan）
        await persistence.save_session(
            session_id, goal, plan=plan_text, status="awaiting_approval",
            auth_boundary_id=auth_boundary_id, tenant_id=tenant_id,
        )
        # 审计：规划已生成
        audit_logger.log(session_id, "plan_created", self._sessions[session_id].get("agent", "agent"), {"plan_length": len(plan_text)}, tenant_id=tenant_id)
        logger.info(f"Session {session_id}: {self._sessions[session_id].get('agent', 'agent')} plan generated")
        return plan_text

    async def execute(self, session_id: str, tenant_id: str | None = None) -> dict:
        """
        人确认规划后，Agent开始执行

        Args:
            session_id: 会话ID
            tenant_id: 所属租户（缺省时从会话上下文回退）

        Returns:
            result: 执行结果
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        # 优先使用显式传入；否则从会话上下文取
        tid = tenant_id or session.get("tenant_id", "default")

        session["status"] = "executing"
        # 落库：AgentSession（executing）
        await persistence.save_session(
            session_id, session["goal"], status="executing",
            plan=session.get("plan"),
            auth_boundary_id=session.get("auth_boundary_id"),
            tenant_id=tid,
        )
        # 审计：人已确认
        from src.meta_agent.audit import audit_logger
        audit_logger.log(session_id, "approved", "human", {"feedback": "Confirmed by human"}, tenant_id=tid)

        goal = session["goal"]
        agent_name = session.get("agent", "supply_chain")

        # 路由到正确的Agent执行
        from src.runtime.agent.router import execute_by_agent
        result = await execute_by_agent(agent_name, goal)

        # ===== AI原生核心：授权边界评估 + 异常介入闭环 =====
        autonomous_actions, pending_interventions = await self._apply_authorization(
            session_id, agent_name, goal, result, tenant_id=tid
        )
        result["autonomous_actions"] = autonomous_actions
        result["pending_interventions"] = pending_interventions

        # ===== AI原生 L2 推理层下沉：执行决策辅助 =====
        # 基于确定性结果（事实锚点）让 LLM 做决策解读/优先级/风险研判；
        # LLM 不可用/失败时 ai_insight=None，前端仅展示纯确定性结果，绝不破坏管道。
        result["ai_insight"], result["ai_insight_source"] = await self._generate_insight(
            agent_name, goal, result, autonomous_actions, pending_interventions
        )

        session["status"] = "completed"
        session["result"] = result
        # 落库：AgentSession（completed + 确定性结果 JSON）——事实锚点完整保留
        await persistence.save_session(
            session_id, goal, plan=session.get("plan"), status="completed",
            result=result, auth_boundary_id=session.get("auth_boundary_id"),
            tenant_id=tid,
        )
        # 审计：执行完成
        audit_logger.log(session_id, "executed", "agent", {
            "summary": result.get("summary", ""),
            "completeness": result.get("completeness_pct"),
            "autonomous": len(autonomous_actions),
            "pending": len(pending_interventions),
        }, tenant_id=tid)

        # ===== 知识图谱增量写入（V1-1）=====
        # 基于确定性执行结果，fire-and-forget 不阻塞执行管道；失败不外溢。
        try:
            from src.runtime import knowledge_graph as kg

            asyncio.create_task(kg.apply_execution_result(tid, agent_name, session_id, result))
        except Exception as e:
            logger.warning(f"知识图谱增量写入调度失败（不破管）：{e}")

        # 发布事件通知
        warnings = result.get("warning", result.get("alerts", []))
        level = "critical" if len(warnings) > 2 else "warning" if warnings else "success"
        title = f"{agent_name} completed"
        message = result.get("summary", "")
        event_bus.publish("agent_complete", title, message, level=level)

        if warnings:
            for w in warnings[:3]:
                event_bus.publish("agent_alert", f"{agent_name} alert", w, level="critical")
        logger.info(f"Session {session_id}: Execution completed")
        return result

    async def _apply_authorization(
        self, session_id: str, agent_name: str, goal: str, result: dict, tenant_id: str = "default"
    ) -> tuple[list[dict], list[dict]]:
        """对执行结果中的动作应用授权边界评估

        Returns:
            (autonomous_actions, pending_interventions)
        """
        from src.runtime.core.authorization import authorization
        from src.runtime.core.intervention import intervention_queue, Intervention
        from src.runtime.core.metrics import metrics
        from src.runtime.models.authorization import PlannedAction
        from src.meta_agent.audit import audit_logger

        # 取边界：优先会话指定，否则取Agent默认（均限定在当前租户内）
        auth_scope = authorization.for_tenant(tenant_id)
        boundary = None
        bid = self._sessions.get(session_id, {}).get("auth_boundary_id")
        if bid:
            boundary = auth_scope.get(bid)
        if boundary is None:
            boundary = auth_scope.get_for_agent(agent_name)
        if boundary is None:
            # 无边界配置：全部视为自主（演示默认行为）
            return [], []

        # 从结果构造待评估动作（通用映射：识别所有 Agent 的 actions_taken）
        # 历史兼容：供应链 lock_alternative -> lock_inventory
        TYPE_ALIASES = {"lock_alternative": "lock_inventory"}
        actions: list[PlannedAction] = []
        for act in result.get("actions_taken", []):
            atype = act.get("type", "")
            ptype = TYPE_ALIASES.get(atype, atype)
            # 品类推断：供应链 lock_alternative 用物料编码转中文品类（匹配白名单）；
            # 其余 Agent 用业务字段，且边界不设品类限制，不触发白名单拦截。
            if atype == "lock_alternative":
                category = self._infer_category(act.get("material", ""))
            else:
                category = (
                    act.get("category")
                    or act.get("line_id")
                    or act.get("target")
                    or act.get("eco_id")
                    or act.get("standard_id")
                    or act.get("case_id")
                    or ""
                )
            actions.append(PlannedAction(
                type=ptype,
                category=category,
                qty=int(act.get("qty", 0)),
                confidence=float(act.get("confidence", 1.0)),
                price_delta_pct=float(act.get("price_delta_pct", 0.0)),
                detail=act.get("detail", ""),
                session_id=session_id,
            ))

        if not actions:
            return [], []

        decisions = auth_scope.evaluate_batch(boundary, actions)

        autonomous: list[dict] = []
        pending: list[dict] = []
        for dec in decisions:
            if dec.decision == "auto":
                autonomous.append({
                    "type": dec.action.type,
                    "detail": dec.action.detail,
                    "status": "auto_executed",
                })
            else:
                ivt = Intervention(
                    session_id=session_id,
                    agent=agent_name,
                    action=dec.action,
                    reason=dec.reason,
                    boundary_id=boundary.id,
                )
                intervention_queue.push(ivt)
                pending.append(ivt.to_dict())
                # 审计：动作因越界被拦截
                audit_logger.log(session_id, "intercepted", "agent", {
                    "action": dec.action.type,
                    "reason": dec.reason,
                }, tenant_id=tenant_id)
                # 事件：推送异常介入
                event_bus.publish(
                    "intervention_required",
                    "待人工审批",
                    f"[{agent_name}] {dec.action.detail} — {dec.reason}",
                    level="warning",
                    source="authorization",
                )

        # 记录效果指标
        metrics.record(
            session_id=session_id,
            agent=agent_name,
            total=len(decisions),
            auto=len(autonomous),
            human=len(pending),
        )

        return autonomous, pending

    async def _generate_insight(
        self,
        agent_name: str,
        goal: str,
        result: dict,
        autonomous_actions: list[dict],
        pending_interventions: list[dict],
    ) -> tuple[str | None, str]:
        """执行阶段的 LLM 决策辅助。返回 (ai_insight, source)。

        source: "llm"（LLM 生成成功）或 "none"（无 LLM/失败，纯确定性结果）。
        """
        from src.common.llm_client import llm_client
        if not llm_client.available:
            return None, "none"

        facts = self._build_fact_summary(result, autonomous_actions, pending_interventions)
        insight = await llm_client.generate_decision_insight(agent_name, goal, facts)
        if insight:
            return insight, "llm"
        return None, "none"

    @staticmethod
    def _build_fact_summary(
        result: dict,
        autonomous_actions: list[dict],
        pending_interventions: list[dict],
    ) -> str:
        """从确定性执行结果提炼紧凑事实摘要，作为 LLM 决策辅助的唯一事实来源。

        只挑关键字段，避免把冗长明细全丢给 LLM（既省 token 也降低幻觉面）。
        """
        lines: list[str] = []
        if result.get("summary"):
            lines.append(f"摘要: {result['summary']}")
        if result.get("completeness_pct") is not None:
            lines.append(f"齐套率/完成度: {result['completeness_pct']}%")
        if result.get("current_yield") is not None:
            lines.append(f"当前良率: {result['current_yield']}% (目标 {result.get('target_yield', 'N/A')}%)")
        if result.get("root_cause"):
            lines.append(f"根因: {result['root_cause']}")

        # 设备健康
        for e in (result.get("equipments") or [])[:5]:
            lines.append(f"设备 {e.get('name','')}: 健康分 {e.get('health_score','')}")
        # 缺陷分布
        for d in (result.get("defects") or [])[:5]:
            lines.append(f"缺陷 {d.get('type','')}: {d.get('ratio','')}% ({d.get('trend','')})")
        # 预警
        warnings = result.get("warning") or result.get("alerts") or []
        for w in warnings[:5]:
            lines.append(f"预警: {w}")

        # 已产出的原始动作（含状态）
        for a in (result.get("actions_taken") or [])[:8]:
            desc = a.get("detail") or a.get("type", "")
            conf = a.get("confidence")
            conf_s = f" 置信度{conf}" if conf is not None else ""
            lines.append(f"动作[{a.get('type','')}]: {desc}{conf_s}")

        # 授权分流结果（决策辅助的关键上下文）
        lines.append(f"已自主执行动作数: {len(autonomous_actions)}")
        lines.append(f"待人工审批动作数: {len(pending_interventions)}")
        for p in pending_interventions[:5]:
            act = p.get("action", {})
            detail = act.get("detail", "") if isinstance(act, dict) else ""
            lines.append(f"待审批: {detail} — 原因: {p.get('reason','')}")

        return "\n".join(lines) if lines else "（无结构化事实）"

    @staticmethod
    def _infer_category(material_code: str) -> str:
        """根据物料编码推断品类（用于边界白名单匹配）"""
        code = material_code.upper()
        if "WAFER" in code or "SI" in code:
            return "硅片"
        if "PR" in code or "RESIST" in code:
            return "光刻胶"
        if "TARGET" in code or "TI" in code:
            return "靶材"
        if "GAS" in code:
            return "特气"
        if "PCB" in code:
            return "PCB"
        return "其他"

    async def reject(self, session_id: str, feedback: str | None = None, tenant_id: str = "default"):
        """人驳回规划"""
        session = self._sessions.get(session_id)
        tid = tenant_id or (session.get("tenant_id", "default") if session else "default")
        if session:
            session["status"] = "rejected"
            session["feedback"] = feedback
            # 落库：AgentSession（rejected）
            await persistence.save_session(
                session_id, session.get("goal", ""), status="rejected",
                plan=session.get("plan"),
                auth_boundary_id=session.get("auth_boundary_id"),
                tenant_id=tid,
            )
            logger.info(f"Session {session_id}: Rejected. Feedback: {feedback}")

    def get_session(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    async def _plan_for_generic_agent(self, agent_name: str, goal: str) -> str:
        """为非供应链Agent生成规划文本"""
        from src.runtime.agent.router import execute_by_agent
        result = await execute_by_agent(agent_name, goal)

        agent_labels = {
            "dfm_check": "DFM检查Agent",
            "bom_selector": "BOM选型Agent",
            "oee_optimizer": "OEE优化Agent",
            "eco_change": "ECO变更Agent",
            "smt_changeover": "SMT换线Agent",
            "aoi_judge": "AOI判定Agent",
            "ipc_standard": "IPC标准Agent",
        }
        label = agent_labels.get(agent_name, agent_name)

        lines = [f"## {label} report\n", f"### Goal\n> {goal}\n", f"### Summary\n{result.get('summary', '')}\n"]

        if "recommendations" in result:
            lines.append("### Recommendations")
            for r in result["recommendations"]:
                lines.append(f"- {r}")

        if "checks" in result:
            lines.append("\n### DFM checks")
            for c in result["checks"]:
                lines.append(f"- {c.get('rule','')}: {c['status']} ({c.get('actual','')} / {c.get('required','')} {c.get('unit','')})")

        if "alternatives" in result:
            lines.append("\n### Alternatives")
            for a in result["alternatives"]:
                lines.append(f"- {a['part_number']} ({a['manufacturer']}): ${a['unit_price']} [{a['compatibility']}]")

        if "lines" in result:
            # 同一份 result 里 key 名 "lines" 被两类 Agent 复用，需按 schema 区分：
            #  - OEE 优化 Agent：产线含 oee/availability/performance/quality
            #  - 能源碳 Agent：产线含 energy_kwh/carbon_t/green_ratio（否则会 KeyError 500）
            sample = result["lines"][0] if result["lines"] else {}
            if "oee" in sample:
                lines.append("\n### Production lines")
                for l in result["lines"]:
                    lines.append(f"- {l['line_name']}: OEE {l['oee']}% (A:{l['availability']}% P:{l['performance']}% Q:{l['quality']}%)")
            elif "energy_kwh" in sample:
                lines.append("\n### 产线能耗与碳排放")
                for l in result["lines"]:
                    lines.append(f"- {l['name']}: 能耗 {l['energy_kwh']} kWh，碳排 {l['carbon_t']} tCO2，绿电 {l['green_ratio']}%")
            # 其它未知 schema 的 lines 不渲染，避免崩溃

        if "defect_categories" in result:
            lines.append("\n### AOI defect categories")
            for c in result["defect_categories"]:
                lines.append(f"- {c['type']}: {c['false_alarm_rate']}% false alarm ({c['false_alarms']}/{c['total_calls']})")

        if "affected_items" in result:
            lines.append("\n### Affected items")
            for i in result["affected_items"]:
                lines.append(f"- {i['category']}: {i.get('part','')} qty={i.get('qty',0)}")

        if "critical_path" in result:
            lines.append("\n### Changeover critical path")
            for s in result["critical_path"]:
                lines.append(f"  {s['step']}. {s['action']} ({s['time_min']}min)")

        if "judgment" in result:
            j = result["judgment"]
            lines.append("\n### IPC judgment")
            lines.append(f"- Defect: {j.get('defect_type','')}")
            lines.append(f"- Class 1: {j.get('class_1_limit','')}")
            lines.append(f"- Class 2: {j.get('class_2_limit','')}")
            lines.append(f"- Class 3: {j.get('class_3_limit','')}")

        lines.append("\n> Confirm to execute?")
        return "\n".join(lines)

    def list_sessions(self, tenant_id: str | None = None) -> list[dict]:
        """列出会话摘要（tenant_id 提供时按租户隔离）"""
        summaries = []
        for sid, s in self._sessions.items():
            if tenant_id and s.get("tenant_id", "default") != tenant_id:
                continue
            summaries.append({
                "session_id": sid,
                "tenant_id": s.get("tenant_id", "default"),
                "goal": s.get("goal", "")[:80],
                "status": s.get("status", "unknown"),
                "completeness": s.get("result", {}).get("completeness_pct") if s.get("result") else None,
            })
        return sorted(summaries, key=lambda x: x.get("session_id", ""), reverse=True)
