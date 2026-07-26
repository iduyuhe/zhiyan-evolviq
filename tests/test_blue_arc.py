"""蓝弧闭环驱动测试（v22 落地入口）。

验证：act 声明动作+预期 → observe 上报实际 → 后果校验（match/!match）→
认知层回流（经验库 + KG 置信度）。状态可观测。
"""
import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.main import app
from src.runtime.consequence import consequence


@pytest.fixture(autouse=True)
def _clear():
    consequence.clear()
    yield
    consequence.clear()


@pytest.fixture
def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_act_then_observe_validated(_client):
    # 声明动作：预期 oee 约 0.90
    r = await _client.post("/blue-arc/act", json={"agent": "oee_agent", "predicted": {"oee": 0.90}})
    assert r.status_code == 200
    action_id = r.json()["action_id"]

    # 上报实际：0.91（5% 容差内 → 匹配）
    r2 = await _client.post("/blue-arc/observe", json={"action_id": action_id, "actual": {"oee": 0.91}})
    assert r2.status_code == 200
    body = r2.json()
    assert body["match"] is True

    st = await _client.get("/blue-arc/status")
    assert st.json()["validated"] >= 1


@pytest.mark.asyncio
async def test_observe_mismatch_contradicted(_client):
    r = await _client.post("/blue-arc/act", json={"agent": "yield_agent", "predicted": {"yield": 0.95}})
    action_id = r.json()["action_id"]
    # 实际 0.70，远超 5% 容差 → 不匹配
    r2 = await _client.post("/blue-arc/observe", json={"action_id": action_id, "actual": {"yield": 0.70}})
    assert r2.json()["match"] is False
    st = await _client.get("/blue-arc/status")
    assert st.json()["contradicted"] >= 1


@pytest.mark.asyncio
async def test_observe_unknown_action_404(_client):
    r = await _client.post("/blue-arc/observe", json={"action_id": "act:nonexist", "actual": {"x": 1}})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_direction_expect_decrease(_client):
    r = await _client.post("/blue-arc/act", json={
        "agent": "quality_agent",
        "predicted": {"_expect_decrease": 0.8, "_target_key": "defect"},
    })
    action_id = r.json()["action_id"]
    # 实际 defect 降到 0.5 → 方向正确
    r2 = await _client.post("/blue-arc/observe", json={"action_id": action_id, "actual": {"defect": 0.5}})
    assert r2.json()["match"] is True
