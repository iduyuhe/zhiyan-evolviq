"""V1-4 控制台策略调参——效果驱动调参闭环测试

验证：
- /strategy 面板聚合（current + effect_signals + suggestions）
- /strategy/suggestions 返回列表
- /strategy/tune 真正改写运行时授权边界 + 审计轨迹增长
- /strategy/history 可查
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_strategy_panel_shape(client):
    r = await client.get("/strategy")
    assert r.status_code == 200
    data = r.json()
    assert "current" in data and isinstance(data["current"], list)
    assert "effect_signals" in data
    assert "suggestions" in data and isinstance(data["suggestions"], list)
    # 11 个 Agent 边界应全部出现在面板
    agents = {c["agent"] for c in data["current"]}
    assert len(agents) >= 11


async def test_strategy_suggestions_is_list(client):
    r = await client.get("/strategy/suggestions")
    assert r.status_code == 200
    assert isinstance(r.json()["suggestions"], list)
    # 无运行数据时不应臆造建议
    assert r.json()["target_autonomous_rate"] == 0.70


async def test_strategy_tune_writes_runtime_boundary(client):
    # 取 supply_chain 当前阈值
    before = await client.get("/auth/boundaries/agent/supply_chain")
    old_th = before.json()["boundary"]["confidence_threshold"]

    # 控制台手动下调到 0.72（应被接受并写入）
    r = await client.post("/strategy/tune", json={
        "agent": "supply_chain",
        "param": "confidence_threshold",
        "value": 0.72,
        "reason": "测试：主动放权",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "applied"
    assert body["new"] == 0.72
    assert body["old"] == old_th

    # 运行时授权边界已真正改变
    after = await client.get("/auth/boundaries/agent/supply_chain")
    assert after.json()["boundary"]["confidence_threshold"] == 0.72

    # 恢复，避免污染其它测试
    await client.post("/strategy/tune", json={
        "agent": "supply_chain", "param": "confidence_threshold",
        "value": old_th, "reason": "测试：还原",
    })


async def test_strategy_tune_clamps_and_rejects_bad_param(client):
    # 置信阈值超出安全区间应被夹紧
    r = await client.post("/strategy/tune", json={
        "agent": "supply_chain", "param": "confidence_threshold",
        "value": 0.01, "reason": "越界夹紧",
    })
    assert r.status_code == 200
    assert r.json()["new"] == 0.50  # CONF_MIN

    # 不支持的参数应 400
    bad = await client.post("/strategy/tune", json={
        "agent": "supply_chain", "param": "no_such_param", "value": 1,
    })
    assert bad.status_code == 400

    # 未知 Agent 应 404
    miss = await client.post("/strategy/tune", json={
        "agent": "ghost_agent", "param": "confidence_threshold", "value": 0.8,
    })
    assert miss.status_code == 404

    # 还原
    await client.post("/strategy/tune", json={
        "agent": "supply_chain", "param": "confidence_threshold",
        "value": 0.8, "reason": "测试：还原",
    })


async def test_strategy_history_grows(client):
    h0 = await client.get("/strategy/history")
    n0 = h0.json()["total"]

    await client.post("/strategy/tune", json={
        "agent": "oee_optimizer", "param": "max_daily_autonomous",
        "value": 25, "reason": "测试：上调日上限",
    })
    h1 = await client.get("/strategy/history")
    assert h1.json()["total"] == n0 + 1
    latest = h1.json()["history"][0]
    assert latest["agent"] == "oee_optimizer"
    assert latest["param"] == "max_daily_autonomous"
    assert latest["new"] == 25

    # 还原
    await client.post("/strategy/tune", json={
        "agent": "oee_optimizer", "param": "max_daily_autonomous",
        "value": 20, "reason": "测试：还原",
    })
