"""T3 · 供应链齐套率 ROI 闭环测试（确定性、离线、零 LLM 依赖）

验证：基准齐套率 < 承诺齐套率；内部一致（风险项/缺料量单调不增）；
事实锚点（所有数字可由种子数据 + 确定性规则复现）；行动类型正确。
"""

import pytest


@pytest.mark.asyncio
async def test_roi_closed_loop():
    from src.agents.supply_chain.agent import SupplyChainAgent

    agent = SupplyChainAgent()
    result = await agent.execute("检查BOM-SMIC-28nm-Logic的齐套率并提升", "plan")

    m = result["metrics"]
    # 1) 闭环成立：基准 < 承诺
    assert m["kitting_rate_before"] < m["kitting_rate_after"], "基准齐套率必须低于承诺齐套率"
    assert m["improvement_pp"] > 0
    # 顶部仪表与 metrics.after 一致
    assert abs(result["completeness_pct"] - m["kitting_rate_after"]) < 0.01

    # 2) 内部单调不增（行动只改善、不恶化）
    assert m["risk_items_before"] >= m["risk_items_after"]
    assert m["shortage_qty_before"] >= m["shortage_qty_after"]
    assert m["delivery_accuracy_before"] <= m["delivery_accuracy_after"]

    # 3) 逐物料前后一致：可用量只增不减，风险只降不升
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    for c in result["check_details"]:
        assert c["available_after"] >= c["available_before"]
        assert order.get(c["risk_after"], 9) <= order.get(c["risk_before"], 9)


@pytest.mark.asyncio
async def test_fact_anchor_reproducible():
    """事实锚点：同输入两次执行，确定性结果完全一致（无随机、无 LLM）"""
    from src.agents.supply_chain.agent import SupplyChainAgent

    agent = SupplyChainAgent()
    r1 = await agent.execute("检查BOM-SMIC-28nm-Logic齐套率", "plan")
    r2 = await agent.execute("检查BOM-SMIC-28nm-Logic齐套率", "plan")

    assert r1["metrics"] == r2["metrics"]
    assert [c["available_after"] for c in r1["check_details"]] == [c["available_after"] for c in r2["check_details"]]
    assert [a["type"] for a in r1["actions_taken"]] == [a["type"] for a in r2["actions_taken"]]


@pytest.mark.asyncio
async def test_actions_authorized_and_typed():
    """行动符合授权边界：auto_locked 单物料不超 1000；其余待批；类型合法"""
    from src.agents.supply_chain.agent import SupplyChainAgent

    agent = SupplyChainAgent()
    result = await agent.execute("提升BOM-SMIC-28nm-Logic齐套率到85%", "plan")

    valid_types = {"confirm_po", "expedite_po", "lock_alternative"}
    for a in result["actions_taken"]:
        assert a["type"] in valid_types
        if a["type"] == "lock_alternative" and a["status"] == "auto_locked":
            assert a["qty"] <= 1000, "授权内自动锁定单物料不得超过 1000 pcs"
        # 任何行动都标注了物料与数量（事实可追溯）
        assert a["material"] and a["qty"] >= 0
