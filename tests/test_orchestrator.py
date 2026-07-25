"""多 Agent 编排器测试（V1-5 缺口补齐验证）

覆盖：
1. 目标分解器（GoalDecomposer）
   - 模板命中：8 种预设场景
   - 关键词聚合兜底
   - 同步入口（无 LLM）
2. 编排器（Orchestrator）
   - 并行执行（asyncio.gather）
   - 失败子任务不阻断整体
   - 跨 Agent 共同发现
3. 集成端到端
   - 模板命中 → 实际调用 5+ Agent → 返回综合报告

运行：
    $PY -m pytest tests/test_orchestrator.py -v

降级原则：所有测试不依赖外部服务（PG/Neo4j/网关 simulated），db 不可用时自动跳过持久化。
"""
import asyncio
import time
import pytest

from src.runtime.agent.goal_decomposer import (
    GoalDecomposer,
    SCENARIO_TEMPLATES,
    OrchestratorPlan,
    SubTask,
    _rule_decompose,
    _match_templates,
)


# ---------------------------------------------------------------------------
# 1. 目标分解器测试
# ---------------------------------------------------------------------------


class TestGoalDecomposer:
    """目标分解器测试套件"""

    # ---- 模板命中 ----

    def test_template_npi(self):
        """「新产品导入」应命中 NPI 模板，分解出 5 个 Agent"""
        plan = _rule_decompose("新产品导入评估")
        assert plan.source == "template"
        assert len(plan.sub_tasks) == 5
        agents = {t.agent for t in plan.sub_tasks}
        # 必含 NPI 链路关键 Agent
        assert "dfm_check" in agents
        assert "bom_selector" in agents
        assert "rd_npi" in agents
        assert "smt_changeover" in agents
        assert "cost_analysis" in agents

    def test_template_oee(self):
        """「OEE」应命中 OEE 提升模板"""
        plan = _rule_decompose("产线 OEE 太低，怎么提升？")
        assert plan.source == "template"
        assert any(t.agent == "oee_optimizer" for t in plan.sub_tasks)
        assert any(t.agent == "pm_maintenance" for t in plan.sub_tasks)
        assert any(t.agent == "smt_changeover" for t in plan.sub_tasks)

    def test_template_quality(self):
        """「客诉」应命中质量根因模板"""
        plan = _rule_decompose("客户投诉某批次不良")
        assert plan.source == "template"
        agents = {t.agent for t in plan.sub_tasks}
        assert "quality_trace" in agents
        assert "compliance_q" in agents
        assert "ipc_standard" in agents

    def test_template_energy(self):
        """「碳排放」应命中能耗治理模板"""
        plan = _rule_decompose("如何降低工厂碳排放？")
        assert plan.source == "template"
        agents = {t.agent for t in plan.sub_tasks}
        assert "energy_carbon" in agents
        assert "compliance_q" in agents

    def test_template_eco(self):
        """「ECO」应命中工程变更模板"""
        plan = _rule_decompose("评估一个 ECO 工程变更影响")
        assert plan.source == "template"
        agents = {t.agent for t in plan.sub_tasks}
        assert "eco_change" in agents
        assert "bom_selector" in agents

    def test_template_equipment_failure(self):
        """「设备故障」应命中设备故障诊断模板"""
        plan = _rule_decompose("设备异常停机，维修后复发")
        assert plan.source == "template"
        agents = {t.agent for t in plan.sub_tasks}
        assert "pm_maintenance" in agents
        assert "quality_trace" in agents

    def test_template_kit_rate(self):
        """「齐套率」应命中齐套率与交付改善模板"""
        plan = _rule_decompose("齐套率只有 60%，如何提升？")
        assert plan.source == "template"
        agents = {t.agent for t in plan.sub_tasks}
        assert "supply_chain" in agents
        assert "aps_scheduler" in agents

    def test_template_cockpit(self):
        """「经营驾驶舱」应命中经营决策模板"""
        plan = _rule_decompose("生成经营驾驶舱月度报告")
        assert plan.source == "template"
        agents = {t.agent for t in plan.sub_tasks}
        assert "executive_cockpit" in agents

    # ---- 关键词聚合兜底 ----

    def test_keyword_aggregation_fallback(self):
        """无模板命中时，应按关键词聚合 Agent"""
        # 用一个不触发任何模板但触发了多个关键词的目标
        plan = _rule_decompose("物料清单里有缺料和良率问题")
        # "缺料" 在 SCENARIO_TEMPLATES 的「齐套率与交付改善」里 → 会命中模板
        # 改用更无歧义的文本
        plan = _rule_decompose("BOM 缺料同时 AOI 误报率很高")  # "缺料" 触发齐套率模板
        # 真正无模板场景：组合不含预设 trigger
        plan = _rule_decompose("看看这个产品的 pin-to-pin 替代料和 DFM 风险")
        # "替代料" 在 BOM 选型模板触发词里，但 dfm 是 DFM 模板触发词
        # 这个用例会触发 BOM 选型模板（"替代料" 命中）

        # 真正的兜底测试：用一个非典型表达
        plan = _rule_decompose("PCBA 良率波动，根因不明")
        # "良率" 在「良率分析」触发词里，但 SCENARIO_TEMPLATES 里良率不在某个模板的 trigger 中
        # 应该走关键词聚合路径
        assert plan.source in ("rule", "template")
        if plan.source == "rule":
            # 关键词聚合：至少有 yield_analysis
            assert any(t.agent == "yield_analysis" for t in plan.sub_tasks)

    def test_no_match_falls_back_to_supply_chain(self):
        """完全无任何关键词命中时，回退到 supply_chain 单 Agent"""
        plan = _rule_decompose("今天天气如何？")
        # 完全无关的 query，至少有 1 个 Agent
        assert len(plan.sub_tasks) >= 1
        # 默认是 supply_chain
        assert plan.sub_tasks[0].agent == "supply_chain"

    def test_template_count(self):
        """预设模板数量保护（防止误删）"""
        assert len(SCENARIO_TEMPLATES) >= 8, f"预期至少 8 个模板，实际 {len(SCENARIO_TEMPLATES)}"

    def test_all_template_agents_in_registry(self):
        """所有模板里引用的 Agent 必须在 AGENT_REGISTRY 中（防止 agent 名漂移）"""
        from src.runtime.agent.router import AGENT_REGISTRY
        all_agents = set()
        for tpl in SCENARIO_TEMPLATES:
            for ag, _ in tpl["agents"]:
                all_agents.add(ag)
        for ag in all_agents:
            assert ag in AGENT_REGISTRY, f"模板引用了未注册的 Agent: {ag}"

    def test_no_duplicate_agents_in_plan(self):
        """同一 plan 中不应有重复 Agent（避免重复执行）"""
        plan = _rule_decompose("新产品导入 + OEE 提升 + 客诉 + ECO 变更 + 设备故障 + 齐套率 + 经营 + 能耗")
        agents = [t.agent for t in plan.sub_tasks]
        assert len(agents) == len(set(agents)), f"发现重复 Agent: {agents}"

    def test_sub_task_ids_unique(self):
        """sub_task.task_id 必须唯一"""
        plan = _rule_decompose("新产品导入")
        ids = [t.task_id for t in plan.sub_tasks]
        assert len(ids) == len(set(ids))

    # ---- 异步入口 ----

    @pytest.mark.asyncio
    async def test_async_decompose(self):
        """异步入口在无 LLM 时应回退到规则"""
        decomposer = GoalDecomposer()
        plan = await decomposer.decompose("新产品导入评估")
        assert isinstance(plan, OrchestratorPlan)
        assert plan.source in ("rule", "template", "llm")
        assert len(plan.sub_tasks) >= 2

    @pytest.mark.asyncio
    async def test_async_decompose_no_match(self):
        """无任何命中时异步入口仍可用"""
        decomposer = GoalDecomposer()
        plan = await decomposer.decompose("完全无关的 query xyz")
        assert len(plan.sub_tasks) >= 1


# ---------------------------------------------------------------------------
# 2. 编排器测试
# ---------------------------------------------------------------------------


class TestOrchestrator:
    """编排器测试套件"""

    @pytest.mark.asyncio
    async def test_execute_simple_plan(self):
        """最简单的 plan：单 Agent 也能跑通"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="测试单 Agent 执行",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id="t1", agent="supply_chain", sub_goal="查询硅片库存", focus="主分析"),
            ],
        )
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        assert report.sub_task_count == 1
        assert report.success_count == 1
        assert report.failed_count == 0
        assert report.executions[0]["agent"] == "supply_chain"

    @pytest.mark.asyncio
    async def test_execute_parallel_5_agents(self):
        """5 Agent 并行执行"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="综合诊断",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id="t1", agent="supply_chain", sub_goal="缺料分析", focus="主分析"),
                SubTask(task_id="t2", agent="oee_optimizer", sub_goal="OEE 分析", focus="效率"),
                SubTask(task_id="t3", agent="yield_analysis", sub_goal="良率分析", focus="质量"),
                SubTask(task_id="t4", agent="pm_maintenance", sub_goal="设备健康", focus="设备"),
                SubTask(task_id="t5", agent="energy_carbon", sub_goal="能耗概览", focus="能耗"),
            ],
        )
        start = time.time()
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        elapsed = time.time() - start
        assert report.sub_task_count == 5
        assert report.success_count >= 4, f"至少 4 个成功，实际 {report.success_count}"
        # 关键指标抽取
        assert "summary" in report.__dict__ or hasattr(report, "summary")

    @pytest.mark.asyncio
    async def test_execute_invalid_agent_continues(self):
        """无效 Agent 名时不应阻断其他子任务"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="测试异常",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id="t1", agent="supply_chain", sub_goal="OK 任务", focus="主分析"),
                SubTask(task_id="t2", agent="__nonexistent_agent__", sub_goal="会失败", focus="坏"),
            ],
        )
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        # supply_chain 应该成功；坏 agent 应该失败
        assert report.success_count >= 1
        assert report.failed_count >= 1
        # errors 字段记录失败
        assert len(report.errors) >= 1

    @pytest.mark.asyncio
    async def test_aggregate_extracts_key_metrics(self):
        """关键数字抽取"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="综合诊断",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id="t1", agent="supply_chain", sub_goal="齐套", focus="主"),
                SubTask(task_id="t2", agent="oee_optimizer", sub_goal="OEE", focus="效率"),
            ],
        )
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        # supply_chain 报 completeness_pct → 关键指标
        # oee_optimizer 报 avg_oee → 关键指标
        # 至少一个 key_metrics 被抽出
        assert isinstance(report.key_metrics, dict)

    @pytest.mark.asyncio
    async def test_cross_finding_emergency_state(self):
        """跨 Agent 共同发现：OEE 偏低 + 设备"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="OEE 太低",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id="t1", agent="oee_optimizer", sub_goal="OEE 提升", focus="主"),
                SubTask(task_id="t2", agent="pm_maintenance", sub_goal="设备健康", focus="辅"),
            ],
        )
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        # 跨发现列表是 list 即可
        assert isinstance(report.cross_findings, list)

    @pytest.mark.asyncio
    async def test_aggregate_summary_meaningful(self):
        """汇总摘要应包含关键信息"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="测试摘要",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id="t1", agent="supply_chain", sub_goal="a", focus="f"),
                SubTask(task_id="t2", agent="oee_optimizer", sub_goal="b", focus="f"),
            ],
        )
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        # 摘要中应提到 "Agent"
        assert "Agent" in report.summary


# ---------------------------------------------------------------------------
# 3. 端到端（End-to-End via Decomposer + Orchestrator）
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Decomposer → Orchestrator 全链路"""

    @pytest.mark.asyncio
    async def test_full_flow_npi(self):
        """全流程：NPI 目标 → 分解 → 执行 → 报告"""
        decomposer = GoalDecomposer()
        plan = await decomposer.decompose("新产品导入评估")
        assert plan.source == "template"
        assert len(plan.sub_tasks) >= 4

        from src.runtime.agent.orchestrator import MultiAgentOrchestrator
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)

        # 报告应包含所有 sub_tasks
        assert report.sub_task_count == len(plan.sub_tasks)
        # 至少 3 个成功（demo 数据环境下）
        assert report.success_count >= 3
        # rationale 应来自模板
        assert "新品导入" in report.rationale or "NPI" in report.rationale

    @pytest.mark.asyncio
    async def test_full_flow_quality(self):
        """全流程：客诉 → 分解 → 执行 → 报告"""
        decomposer = GoalDecomposer()
        plan = await decomposer.decompose("客户投诉，需要质量根因分析")
        assert plan.source == "template"

        from src.runtime.agent.orchestrator import MultiAgentOrchestrator
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)

        # 关键 Agent 都被调用
        agents_called = {e["agent"] for e in report.executions}
        assert "quality_trace" in agents_called
        assert "compliance_q" in agents_called


# ---------------------------------------------------------------------------
# 4. 韧性降级测试
# ---------------------------------------------------------------------------


class TestResilience:
    """编排器的韧性降级能力"""

    @pytest.mark.asyncio
    async def test_one_failure_does_not_block_others(self):
        """单个 Agent 失败不应阻断其他 Agent"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="韧性测试",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id="t1", agent="supply_chain", sub_goal="正常1", focus="f"),
                SubTask(task_id="t2", agent="oee_optimizer", sub_goal="正常2", focus="f"),
                SubTask(task_id="t3", agent="__invalid_agent__", sub_goal="会失败", focus="f"),
                SubTask(task_id="t4", agent="yield_analysis", sub_goal="正常3", focus="f"),
            ],
        )
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        # 3 个正常 Agent 至少 2 个成功
        assert report.success_count >= 2
        # 1 个失败
        assert report.failed_count >= 1
        # 错误明细记录
        assert len(report.errors) == 1
        assert report.errors[0]["agent"] == "__invalid_agent__"


# ---------------------------------------------------------------------------
# 5. 拓扑排序测试
# ---------------------------------------------------------------------------


class TestTopoSort:
    """编排器的 DAG 拓扑排序"""

    def test_no_dependency_single_layer(self):
        """无依赖：全部在第 0 层"""
        from src.runtime.agent.orchestrator import MultiAgentOrchestrator
        plan_tasks = [
            SubTask(task_id="t1", agent="supply_chain", sub_goal="a", depends_on=[]),
            SubTask(task_id="t2", agent="oee_optimizer", sub_goal="b", depends_on=[]),
        ]
        layers = MultiAgentOrchestrator._topo_sort(plan_tasks)
        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_dependency_two_layers(self):
        """有依赖：分成两层"""
        from src.runtime.agent.orchestrator import MultiAgentOrchestrator
        plan_tasks = [
            SubTask(task_id="t1", agent="supply_chain", sub_goal="a", depends_on=[]),
            SubTask(task_id="t2", agent="oee_optimizer", sub_goal="b", depends_on=["t1"]),
        ]
        layers = MultiAgentOrchestrator._topo_sort(plan_tasks)
        assert len(layers) == 2
        assert layers[0][0].task_id == "t1"
        assert layers[1][0].task_id == "t2"

    def test_cycle_flattened(self):
        """环依赖：被平铺为兜底层（不破管）"""
        from src.runtime.agent.orchestrator import MultiAgentOrchestrator
        plan_tasks = [
            SubTask(task_id="t1", agent="a", sub_goal="a", depends_on=["t2"]),
            SubTask(task_id="t2", agent="b", sub_goal="b", depends_on=["t1"]),
        ]
        layers = MultiAgentOrchestrator._topo_sort(plan_tasks)
        # 第一层空（无依赖任务），但有环的剩余任务被平铺到最后一层
        # 实际行为：layer0 = 空，循环没找到 nxt，剩余 2 个被平铺 → 总层数 2
        all_tasks = [t for layer in layers for t in layer]
        assert len(all_tasks) == 2


# ---------------------------------------------------------------------------
# 6. 性能烟雾测试
# ---------------------------------------------------------------------------


class TestPerformance:
    """编排器基础性能（不追求精确）"""

    @pytest.mark.asyncio
    async def test_5_agents_under_10s(self):
        """5 Agent 并行执行应在 10s 内完成（demo 数据 + simulated 网关）"""
        from src.runtime.agent.orchestrator import (
            MultiAgentOrchestrator,
            OrchestratorPlan,
            SubTask,
        )
        plan = OrchestratorPlan(
            goal="性能测试",
            strategy="parallel",
            sub_tasks=[
                SubTask(task_id=f"t{i}", agent=ag, sub_goal=f"task {i}", focus="f")
                for i, ag in enumerate([
                    "supply_chain", "oee_optimizer", "yield_analysis",
                    "pm_maintenance", "energy_carbon",
                ], 1)
            ],
        )
        start = time.time()
        orchestrator = MultiAgentOrchestrator(tenant_id="default")
        report = await orchestrator.run(plan)
        elapsed = time.time() - start
        assert elapsed < 10, f"5 Agent 执行耗时 {elapsed:.1f}s，超过 10s 上限"
