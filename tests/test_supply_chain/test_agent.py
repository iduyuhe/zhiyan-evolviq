"""供应链Agent测试"""

import pytest


@pytest.mark.asyncio
async def test_agent_analyze_goal():
    """测试目标分析→规划生成"""
    from src.agents.supply_chain.agent import supply_chain_agent
    plan = await supply_chain_agent.analyze_goal(
        goal="检查BOM-NPI-007的物料齐套，发现缺料风险>30%时自动检索替代方案，在5%价格波动内直接锁定库存"
    )
    assert plan is not None
    assert "规划" in plan or "步骤" in plan or "Plan" in plan
    assert len(plan) > 100


@pytest.mark.asyncio
async def test_agent_execute():
    """测试Agent执行完整流程"""
    from src.agents.supply_chain.agent import supply_chain_agent
    result = await supply_chain_agent.execute(
        goal="检查BOM-NPI-007的物料齐套",
        plan="测试规划"
    )
    assert result["status"] == "completed"
    assert "completeness_pct" in result
    assert len(result["check_details"]) > 0
    assert result["check_details"][0]["material"] is not None
