"""质量决策脑 QualityBrain 测试（强化 P0）

覆盖：
① analyze() 返回五类干预 + 人留终审闸门
② 所有 actions_taken 必须 requires_human_approval=True / auto_executable=False
③ ingest_event() 按 UNS 事件类型映射干预类，并保证五类齐全
④ 子 Agent 不可达（degraded）时主脑不崩溃、零误报动作
"""

import pytest

from src.agents.quality_brain.agent import QualityBrainAgent, quality_brain_agent
from src.agents.quality_brain.tools import (
    EVENT_TO_INTERVENTIONS,
    intervention_order,
)

FIVE = set(intervention_order())


def _async(value):
    """把普通值包成 async 函数，用于确定性替换（绕过真实子 Agent 聚合）。"""
    async def _fn(goal):
        return value
    return _fn


# 合成「四子 Agent 正常工作」的聚合结果（用于确定性编排测试）
WORKING_SUB = {
    "trace": {"status": "completed", "root_cause": "颗粒污染", "severity": "high"},
    "aoi": {"status": "completed", "false_alarm_rate": 25},
    "yield": {"status": "completed", "defects": [{"trend": "上升中"}], "gap": 3},
    "compliance": {"status": "completed", "capa_tasks": [{"type": "create_capa"}]},
}

# 合成「四子 Agent 全部不可达」的聚合结果（韧性测试）
DEGRADED_SUB = {
    "trace": {"status": "degraded", "reason": "unreachable"},
    "aoi": {"status": "degraded", "reason": "unreachable"},
    "yield": {"status": "degraded", "reason": "unreachable"},
    "compliance": {"status": "degraded", "reason": "unreachable"},
}


@pytest.mark.asyncio
async def test_analyze_contract_five_interventions():
    """analyze() 必须返回五类干预且人留终审。"""
    agent = QualityBrainAgent()
    agent._aggregate = _async(WORKING_SUB)  # 确定性：绕开真实子Agent
    result = await agent.analyze("分析晶圆厂质量风险")
    assert result["status"] == "completed"
    ivs = result["five_interventions"]
    assert {i["type"] for i in ivs} == FIVE, "五类干预必须齐全"
    assert result["human_approval_required"] is True
    print(f"  ✅ analyze 五类干预: {[i['label'] for i in ivs]}")


@pytest.mark.asyncio
async def test_actions_require_human_approval():
    """所有动作必须人留终审，不代签放行。"""
    agent = QualityBrainAgent()
    agent._aggregate = _async(WORKING_SUB)
    result = await agent.analyze("分析质量")
    actions = result["actions_taken"]
    assert actions, "正常工作时应至少生成一项干预动作"
    for a in actions:
        assert a["requires_human_approval"] is True
        assert a["auto_executable"] is False
        assert a["status"] == "pending_approval"
    print(f"  ✅ 人留终审闸门: {len(actions)} 项动作全部待人工确认")


@pytest.mark.asyncio
async def test_ingest_event_aoi_maps_and_fills():
    """UNS[aoi] 事件应触发 误报抑制+缺陷预警，并补全五类。"""
    agent = QualityBrainAgent()
    res = await agent.ingest_event({
        "event_type": "aoi", "payload": {}, "channel": "equipment", "tenant_id": "x",
    })
    ivs = res["five_interventions"]
    types = {i["type"] for i in ivs}
    assert types == FIVE, "事件入口也必须保证五类齐全"
    assert "false_alarm_suppression" in types
    assert "defect_forecast" in types
    for a in res["actions_taken"]:
        assert a["requires_human_approval"] is True
    print(f"  ✅ UNS[aoi] 映射: {[i['label'] for i in ivs if i['confidence'] > 0]}")


@pytest.mark.asyncio
async def test_ingest_event_unknown_falls_back():
    """未知事件类型回退到默认干预类，仍保证五类齐全。"""
    agent = QualityBrainAgent()
    res = await agent.ingest_event({"event_type": "mystery"})
    assert {i["type"] for i in res["five_interventions"]} == FIVE


def test_event_to_interventions_catalog_consistency():
    """EVENT_TO_INTERVENTIONS 引用的干预类必须都在目录内。"""
    for et, cats in EVENT_TO_INTERVENTIONS.items():
        for c in cats:
            assert c in FIVE, f"事件[{et}]引用了未定义干预类 {c}"


@pytest.mark.asyncio
async def test_sub_agent_degradation_safe():
    """子 Agent 全部不可达时：主脑不崩溃、五类仍占位移位、零误报动作。"""
    agent = QualityBrainAgent()
    ivs = agent._build_interventions(DEGRADED_SUB, "goal")
    assert {i["type"] for i in ivs} == FIVE
    # 降级来源 → confidence=0.0 → _gate 全部抑制
    for i in ivs:
        assert i["confidence"] == 0.0
    actions = agent._gate(ivs)
    assert actions == [], "降级时不应产生任何待执行动作（安全空输出）"
    print("  ✅ 子Agent全降级: 主脑不崩溃，零误报动作")


@pytest.mark.asyncio
async def test_aggregate_real_no_crash():
    """真实 _aggregate 路径（含延迟 import + safe() 降级）不崩溃。"""
    agent = QualityBrainAgent()
    sub = await agent._aggregate("分析质量")
    assert set(sub.keys()) == {"trace", "aoi", "yield", "compliance"}
    for v in sub.values():
        assert isinstance(v, dict) and "status" in v
    print(f"  ✅ 真实聚合路径: 四子Agent状态 {[v['status'] for v in sub.values()]}")


def test_singleton_exported():
    """单例导出可用，符合 BaseAgent 契约。"""
    assert quality_brain_agent.name == "quality_brain"
    assert hasattr(quality_brain_agent, "analyze")
