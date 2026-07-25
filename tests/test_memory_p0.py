"""P0 记忆闭环测试：编排洞察落库 / 执行经验写回 / 记忆召回 / 指标审计持久化。

运行：pytest tests/test_memory_p0.py -v
"""
import asyncio

import pytest

from src.common import neo4j_client as neo
from src.runtime import knowledge_graph as kg
from src.runtime.core import metrics as metrics_mod
from src.meta_agent import audit as audit_mod
from src.runtime.core.metrics import metrics
from src.meta_agent.audit import audit_logger


@pytest.fixture(autouse=True)
async def _init_neo():
    """确保图谱处于内存模式（沙箱无 Neo4j），并清空。"""
    await neo.init_neo4j()
    await neo.clear_graph()
    yield
    await neo.clear_graph()


# ---------------------------------------------------------------------------
# 1. 编排洞察落库（修复 apply_orchestration_result 缺失 bug）
# ---------------------------------------------------------------------------

async def test_apply_orchestration_result_writes_insights():
    plan = {"goal": "新品导入评估", "strategy": "parallel"}
    report = {
        "sub_task_count": 5,
        "success_count": 5,
        "failed_count": 0,
        "executions": [
            {"agent": "dfm_check", "status": "completed"},
            {"agent": "bom_selector", "status": "completed"},
        ],
        "cross_findings": ["DFM 与 BOM 协同发现：某接插件间距不足，需改版"],
        "priority_actions": [
            {"source_agent": "dfm_check", "detail": "调整接插件间距至 ≥1.2mm", "type": "recommendation"},
        ],
        "key_metrics": {"avg_oee": 78.7},
    }
    await kg.apply_orchestration_result("t1", "sess-orch-1", plan, report)

    # Orchestration 节点
    orch = await neo.get_node("ORCH:sess-orch-1")
    assert orch is not None, "Orchestration 节点应被写入"
    assert orch["props"]["goal"] == "新品导入评估"

    # 跨域洞察 → Insight 节点
    insights = await neo.query_nodes("Insight", tenant="t1")
    texts = [n["props"]["text"] for n in insights]
    assert any("接插件间距" in t for t in texts), f"跨域洞察应落为 Insight，实际：{texts}"
    assert any("调整接插件间距" in t for t in texts), "优先级动作也应落为 Insight"


async def test_apply_orchestration_result_is_resilient_on_missing_func():
    # 该函数此前缺失会导致 engine 静默失败；这里确认调用不再抛异常
    plan = {"goal": "g", "strategy": "parallel"}
    report = {"sub_task_count": 1, "success_count": 1, "failed_count": 0,
              "executions": [], "cross_findings": [], "priority_actions": [], "key_metrics": {}}
    # 不应抛异常
    await kg.apply_orchestration_result("t1", "sess-x", plan, report)


# ---------------------------------------------------------------------------
# 2. 执行经验写回（扩展 apply_execution_result）
# ---------------------------------------------------------------------------

async def test_apply_execution_result_generic_insight():
    result = {"status": "completed", "summary": "硅片良率持续偏低，建议排查光刻工序",
              "insights": ["涂布厚度不均可能是根因"]}
    await kg.apply_execution_result("t1", "yield_analysis", "sid-y1", result)

    insights = await neo.query_nodes("Insight", tenant="t1")
    texts = [n["props"]["text"] for n in insights]
    assert any("硅片良率" in t for t in texts)
    assert any("涂布厚度" in t for t in texts)


async def test_apply_execution_result_structural_oee():
    result = {"status": "completed", "lines": [{"line_id": "L7", "oee": 81.3}]}
    await kg.apply_execution_result("t1", "oee_optimizer", "sid-o1", result)
    node = await neo.get_node("OEE:L7")
    assert node is not None, "OEE 最新值应写入 OEERecord"
    assert node["props"]["oee"] == 81.3


async def test_apply_execution_result_structural_energy():
    result = {"status": "completed", "lines": [{"line_id": "L3", "energy_kwh": 4200, "carbon_t": 2.1}]}
    await kg.apply_execution_result("t1", "energy_carbon", "sid-e1", result)
    node = await neo.get_node("NRG:L3")
    assert node is not None
    assert node["props"]["energy_kwh"] == 4200


async def test_apply_execution_result_tenant_isolation():
    await kg.apply_execution_result("tenantA", "yield_analysis", "s1",
                                     {"summary": "A租户机密结论"})
    await kg.apply_execution_result("tenantB", "yield_analysis", "s2",
                                     {"summary": "B租户机密结论"})
    a_nodes = await neo.query_nodes("Insight", tenant="tenantA")
    b_nodes = await neo.query_nodes("Insight", tenant="tenantB")
    assert len(a_nodes) == 1 and len(b_nodes) == 1
    assert "A租户" in a_nodes[0]["props"]["text"]
    # 跨租户不可见
    assert all("B租户" not in n["props"]["text"] for n in a_nodes)


# ---------------------------------------------------------------------------
# 3. 记忆召回闭环（recall 读回历史经验）
# ---------------------------------------------------------------------------

async def test_recall_reads_back_written_insight():
    from src.runtime.memory import recall
    await kg.apply_execution_result("t1", "quality_trace", "s1",
                                    {"summary": "光刻机偏移导致套刻偏差，根因已定位"})
    mem = await recall("光刻机套刻偏差怎么处理", tenant_id="t1")
    assert len(mem["insights"]) > 0, "应召回刚写入的经验"
    assert any("光刻机" in t for t in mem["insights"])


async def test_recall_empty_when_no_match():
    from src.runtime.memory import recall
    mem = await recall("完全无关的主题xyz", tenant_id="t1")
    assert mem["insights"] == []


# ---------------------------------------------------------------------------
# 4. BaseAgent.recall 钩子
# ---------------------------------------------------------------------------

async def test_base_agent_recall_hook():
    from src.agents.base import BaseAgent

    class DummyAgent(BaseAgent):
        name = "dummy"

        async def analyze(self, goal: str) -> dict:
            return {"status": "completed", "summary": "ok"}

    await kg.apply_execution_result("t1", "dummy", "s1", {"summary": "Dummy 历史经验可用"})
    agent = DummyAgent()
    mem = await agent.recall("Dummy 历史", tenant_id="t1")
    assert any("Dummy 历史经验" in t for t in mem["insights"])


# ---------------------------------------------------------------------------
# 5. metrics / audit 持久化与回灌
# ---------------------------------------------------------------------------

async def test_metrics_record_and_report():
    metrics._records.clear()
    metrics.record("s1", "supply_chain", total=10, auto=8, human=2, tenant="t1")
    rep = metrics.effect_report()
    assert rep["total_actions"] == 10
    assert rep["auto_actions"] == 8
    assert rep["autonomous_rate"] == 0.8


async def test_metrics_persist_sink_called(monkeypatch):
    called = {}

    async def fake_sink(kind, agent, summary, payload, tenant):
        called["n"] = called.get("n", 0) + 1
        called["kind"] = kind

    metrics.attach_sink(fake_sink)
    metrics._records.clear()
    # 模拟有运行循环的场景：用 asyncio 直接驱动
    await asyncio.sleep(0)  # 确保有运行循环
    metrics.record("s1", "cost_analysis", total=5, auto=4, human=1, tenant="t1")
    # 给 fire-and-forget 任务一点时间
    await asyncio.sleep(0.05)
    assert called.get("n", 0) >= 1, "落库 sink 应被调用"
    assert called["kind"] == "action"
    metrics.attach_sink(None)  # 复原


async def test_audit_hydrate_and_get_logs():
    audit_logger._logs.clear()
    audit_logger.log("s1", "goal_set", "human", {"goal": "测试"}, tenant_id="t1")
    assert len(audit_logger.get_logs()) == 1
    # hydrate 在无 db 时回灌空（不破管）
    n = await audit_logger.hydrate(limit=10)
    assert isinstance(n, int)


async def test_metrics_hydrate_resilient():
    # 无 db / 无 sink 时 hydrate 不抛异常
    n = await metrics.hydrate(limit=10)
    assert isinstance(n, int)
