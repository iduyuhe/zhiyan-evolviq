"""S3-1 #315：行为埋点基座专项测试

覆盖：
- behavior_store：record / events_for 租户隔离 / profile 聚合 / 非法输入不炸
- API：POST /behavior/event（埋点上报）/ GET /behavior/profile（画像）
- 权限门：GET /behavior/events 仅管理员（viewer 403）
- 🔴 隐私红线：租户 A 的事件绝不出现在租户 B 的事件流/画像中
- agent 会话起点钩子：POST /sessions 自动记 agent_session 事件（埋点失败不阻断主流程）
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.behavior_store import behavior_store

pytestmark = pytest.mark.asyncio

TEST_ADMIN_PW = "TestAdmin123!"
TENANT_A = "BEHAV_TENANT_A"
TENANT_B = "BEHAV_TENANT_B"


# 隔离：behavior_store 是进程级单例，每个测试前后清空内存池，
# 防止本文件事件泄漏进其他测试（以及其他测试的会话钩子事件泄漏进来）。
@pytest.fixture(autouse=True)
def _isolate_store():
    behavior_store.clear_memory()
    yield
    behavior_store.clear_memory()


def _client():
    from src.runtime.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _admin_token() -> str:
    from src.runtime.authn.service import authn_service

    await authn_service.ensure_admin(password=TEST_ADMIN_PW)
    async with _client() as c:
        r = await c.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})
        return r.json()["access_token"]


# ---------------------------------------------------------------------------
# store 层
# ---------------------------------------------------------------------------


async def test_record_and_events_for():
    rec = await behavior_store.record(
        tenant_id=TENANT_A, event_type="Signal_View ", user_id="u1",
        object_kind="panel", object_id="env_perception", meta={"k": "v"},
    )
    assert rec is not None
    assert rec["event_type"] == "signal_view"  # 规整小写+去空白
    items = behavior_store.events_for(TENANT_A)
    assert len(items) == 1 and items[0]["object_id"] == "env_perception"


async def test_record_invalid_never_raises():
    """埋点失败≠业务失败：空租户/空类型只返回 None，绝不抛异常。"""
    assert await behavior_store.record(tenant_id="", event_type="x") is None
    assert await behavior_store.record(tenant_id=TENANT_A, event_type="") is None
    # meta 不可序列化也不炸
    rec = await behavior_store.record(tenant_id=TENANT_A, event_type="t", meta={"bad": object()})
    assert rec is not None and rec["meta"] is None


async def test_tenant_isolation():
    """🔴 隐私红线：A 的事件绝不出现在 B 的事件流与画像。"""
    await behavior_store.record(tenant_id=TENANT_A, event_type="signal_view", user_id="ua")
    await behavior_store.record(tenant_id=TENANT_B, event_type="agent_session", user_id="ub")
    a_items = behavior_store.events_for(TENANT_A)
    b_items = behavior_store.events_for(TENANT_B)
    assert {i["tenant_id"] for i in a_items} == {TENANT_A}
    assert {i["tenant_id"] for i in b_items} == {TENANT_B}
    pa = behavior_store.profile(TENANT_A)
    assert pa["total_events"] == 1 and "agent_session" not in pa["event_types"]


async def test_profile_aggregation():
    for _ in range(3):
        await behavior_store.record(
            tenant_id=TENANT_A, event_type="signal_view", user_id="u1",
            object_kind="panel", object_id="env_perception",
        )
    await behavior_store.record(
        tenant_id=TENANT_A, event_type="agent_session", user_id="u2",
        object_kind="agent", object_id="cost_analysis",
    )
    p = behavior_store.profile(TENANT_A)
    assert p["total_events"] == 4
    assert p["event_types"] == {"signal_view": 3, "agent_session": 1}
    assert p["top_objects"][0] == {"object": "panel:env_perception", "count": 3}
    assert p["active_users"] == 2
    assert p["events_last_7d"] == 4


# ---------------------------------------------------------------------------
# API 层
# ---------------------------------------------------------------------------


async def test_api_report_and_profile():
    async with _client() as c:
        r = await c.post(
            "/behavior/event",
            json={"event_type": "signal_view", "object_kind": "panel", "object_id": "env_perception"},
            headers={"X-Tenant-Key": TENANT_A},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "recorded"
        assert r.json()["event"]["tenant_id"] == TENANT_A

        p = await c.get("/behavior/profile", headers={"X-Tenant-Key": TENANT_A})
        assert p.status_code == 200
        assert p.json()["event_types"].get("signal_view") == 1

        # 空 event_type → 400（唯一硬校验）
        bad = await c.post("/behavior/event", json={"event_type": "  "}, headers={"X-Tenant-Key": TENANT_A})
        assert bad.status_code == 400


async def test_api_events_admin_gate():
    """事件流明细（含 user_id）仅管理员可见；匿名 viewer → 403。"""
    await behavior_store.record(tenant_id="default", event_type="signal_view")
    async with _client() as c:
        r = await c.get("/behavior/events")  # 匿名=viewer
        assert r.status_code == 403
        token = await _admin_token()
        r2 = await c.get("/behavior/events", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1


async def test_api_profile_tenant_scoped():
    """画像只回本租户：B 上报后，A 的画像不受影响。"""
    async with _client() as c:
        await c.post("/behavior/event", json={"event_type": "signal_pull"}, headers={"X-Tenant-Key": TENANT_B})
        p = await c.get("/behavior/profile", headers={"X-Tenant-Key": TENANT_A})
        assert p.json()["total_events"] == 0


# ---------------------------------------------------------------------------
# agent 会话起点钩子
# ---------------------------------------------------------------------------


async def test_session_hook_records_agent_session():
    async with _client() as c:
        r = await c.post("/sessions", json={"goal": "产量分析"})
        assert r.status_code == 200
    items = behavior_store.events_for("default", event_type="agent_session")
    assert len(items) == 1
    ev = items[0]
    assert ev["object_kind"] == "agent"
    assert ev["meta"] and "产量分析" in ev["meta"]


async def test_session_hook_failure_never_blocks(monkeypatch):
    """埋点内部炸了也不影响会话主流程（fire-and-forget 语义验证）。"""

    async def _boom(*a, **k):  # noqa: ANN001
        raise RuntimeError("埋点故障注入")

    monkeypatch.setattr(behavior_store, "_persist", _boom)
    async with _client() as c:
        r = await c.post("/sessions", json={"goal": "产量分析"})
        assert r.status_code == 200  # record() 吞掉持久化异常
