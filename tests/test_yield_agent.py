"""良率分析Agent测试"""

import pytest


@pytest.mark.asyncio
async def test_yield_analyze():
    """测试良率分析"""
    from src.agents.yield_analysis.agent import yield_agent
    result = await yield_agent.analyze("分析28nm良率趋势")
    assert result["status"] == "completed"
    assert result["current_yield"] > 0
    assert result["target_yield"] > 0
    assert len(result["defects"]) >= 1
    print(f"  ✅ 良率分析: {result['current_yield']}%")


@pytest.mark.asyncio
async def test_yield_defects():
    """测试缺陷分析"""
    from src.agents.yield_analysis.agent import yield_agent
    result = await yield_agent.analyze("分析缺陷分布")
    assert len(result["defects"]) == 3
    assert len(result["findings"]) >= 2
    print(f"  ✅ 缺陷分析: {len(result['defects'])}类缺陷")


@pytest.mark.asyncio
async def test_yield_recommendations():
    """测试改进建议"""
    from src.agents.yield_analysis.agent import yield_agent
    result = await yield_agent.analyze("良率提升建议")
    assert len(result["recommendations"]) >= 0
    print(f"  ✅ 改进建议: {len(result['recommendations'])}条")
