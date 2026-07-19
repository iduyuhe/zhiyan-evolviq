"""Runtime API集成测试"""

from httpx import AsyncClient, ASGITransport
import pytest


@pytest.fixture
def client():
    from src.runtime.main import app
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "智衍 EvolvIQ Runtime"


@pytest.mark.asyncio
async def test_create_session(client):
    resp = await client.post("/sessions", json={
        "goal": "检查BOM-NPI-007物料齐套",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "awaiting_approval"
    assert "plan" in data


@pytest.mark.asyncio
async def test_approve_session(client):
    # 创建session
    create_resp = await client.post("/sessions", json={
        "goal": "检查BOM-NPI-007物料齐套",
    })
    session_id = create_resp.json()["session_id"]

    # 批准
    resp = await client.post(f"/sessions/{session_id}/approve", json={
        "approved": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id


@pytest.mark.asyncio
async def test_meta_agent_monitor():
    """测试元Agent监控"""
    from src.meta_agent.monitor import monitor
    health = monitor.get_health()
    assert health.status in ("healthy", "degraded")
    assert health.uptime_seconds >= 0
