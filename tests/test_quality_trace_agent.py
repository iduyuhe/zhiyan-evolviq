"""质量追溯Agent测试"""

import pytest


@pytest.mark.asyncio
async def test_trace_basic():
    """测试基本追溯"""
    from src.agents.quality_trace.agent import quality_trace_agent
    result = await quality_trace_agent.trace("trace quality issue")
    assert "trace_path" in result
    assert len(result["trace_path"]) >= 1
    assert "suspected_equipments" in result
    print(f"  ✅ 质量追溯: {len(result['trace_path'])}步路径")


@pytest.mark.asyncio
async def test_trace_case_match():
    """测试案例匹配"""
    from src.agents.quality_trace.agent import quality_trace_agent
    result = await quality_trace_agent.trace("颗粒污染")
    assert "trace_path" in result
    assert len(result["suspected_equipments"]) >= 1
    print(f"  ✅ 案例匹配: {result['id']} (场景: 颗粒污染)")


@pytest.mark.asyncio
async def test_trace_root_cause():
    """测试根因输出"""
    from src.agents.quality_trace.agent import quality_trace_agent
    result = await quality_trace_agent.trace("刻蚀深度")
    assert "trace_path" in result
    assert result.get("root_cause") != ""
    assert "fix_actions" in result
    print(f"  ✅ 根因分析: {result['root_cause'][:30]}...")
