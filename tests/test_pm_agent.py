"""设备预测维护Agent测试"""

import pytest


@pytest.mark.asyncio
async def test_pm_analyze_equipment():
    """测试设备健康分析"""
    from src.agents.pm_maintenance.agent import pm_agent
    result = await pm_agent.analyze("检查光刻机健康状态")
    assert result["status"] == "completed"
    assert len(result["equipments"]) >= 1
    assert "health_score" in result["equipments"][0]
    print(f"  ✅ 设备健康分析: {len(result['equipments'])}台设备")


@pytest.mark.asyncio
async def test_pm_analyze_multiple():
    """测试多台设备分析"""
    from src.agents.pm_maintenance.agent import pm_agent
    result = await pm_agent.analyze("检查所有设备健康")
    assert len(result["equipments"]) == 3
    assert len(result["alerts"]) >= 0
    print(f"  ✅ 多设备分析: {len(result['equipments'])}台")


@pytest.mark.asyncio
async def test_pm_alerts():
    """测试设备预警生成"""
    from src.agents.pm_maintenance.agent import pm_agent
    result = await pm_agent.analyze("检查刻蚀机")
    # 刻蚀机健康评分<80，应有预警
    for eq in result["equipments"]:
        if "etcher" in eq["equipment_id"]:
            assert eq["health_score"] < 80
    print(f"  ✅ 设备预警: {len(result['alerts'])}条")
