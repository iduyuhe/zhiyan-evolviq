"""S3-6 共生进化环（#320，MASTER §3.6）测试

覆盖：
- 脱敏：邮箱/手机号/租户标识被剥离
- submit_feedback：落库 + 返回 tracking_id + 48h SLA 计时
- feedback_status / growth_profile / evolution_notifications 聚合正确
- mark_released：推进到 released → 进化回告出现
- 🔴 租户隔离：A 的反馈不进 B 的档案/状态
- API 集成（FastAPI TestClient，auth override + tenant contextvar）
"""
from __future__ import annotations

import os
import sys
import asyncio

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _clear():
    from src.runtime.behavior_store import behavior_store
    from src.runtime import symbiosis_store
    behavior_store._events = []
    # 不真打 GitHub：返回假 Issue，避免测试污染公开仓库
    symbiosis_store._gh_create_issue = lambda title, body: {
        "number": 99001,
        "html_url": "https://github.com/iduyuhe/zhiyan-evolviq/issues/99001",
    }
    yield
    behavior_store._events = []


def test_redact_strips_pii():
    from src.runtime.symbiosis_store import _redact
    t = _redact("联系 du@acme.com 或 13800138000，租户 t-default 的数据", "t-default")
    assert "du@acme.com" not in t
    assert "13800138000" not in t
    assert "t-default" not in t
    assert "已脱敏" in t


@pytest.mark.asyncio
async def test_submit_returns_tracking_and_sla():
    from src.runtime.symbiosis_store import submit_feedback, feedback_status
    v = await submit_feedback("tA", "alice", "idea", "希望增加替代料推荐", anonymous=True)
    assert v["tracking_id"].startswith("fb_")
    assert v["status"] == "submitted"
    assert v["anonymous"] is True
    assert v["needs_review"] is True
    assert v["sla_hours"] == 48
    assert v["sla_remaining_hours"] is not None
    assert v["sla_remaining_hours"] <= 48.0
    items = feedback_status("tA")
    assert len(items) == 1
    assert items[0]["tracking_id"] == v["tracking_id"]


@pytest.mark.asyncio
async def test_mark_released_then_evolution():
    from src.runtime.symbiosis_store import (
        submit_feedback,
        feedback_status,
        evolution_notifications,
        mark_released,
    )
    v = await submit_feedback("tA", "alice", "idea", "建议加 BOM 成本趋势图", anonymous=True)
    tid = v["tracking_id"]
    ok = await mark_released("tA", tid, "v31.2")
    assert ok is True
    items = feedback_status("tA")
    rel = [x for x in items if x["status"] == "released"]
    assert len(rel) == 1
    assert rel[0]["released_version"] == "v31.2"
    evos = evolution_notifications("tA")
    assert len(evos) == 1
    assert "v31.2" in evos[0]["message"]
    assert evos[0]["version"] == "v31.2"


@pytest.mark.asyncio
async def test_tenant_isolation():
    from src.runtime.symbiosis_store import (
        submit_feedback,
        feedback_status,
        growth_profile,
    )
    await submit_feedback("tA", "alice", "idea", "A 的反馈", anonymous=True)
    # B 无任何反馈
    assert feedback_status("tB") == []
    gp_b = growth_profile("tB")
    assert gp_b["feedback_contributed"] == 0
    gp_a = growth_profile("tA")
    assert gp_a["feedback_contributed"] >= 1  # 建 Issue 成功或失败都计内网反馈


@pytest.mark.asyncio
async def test_growth_profile_fields():
    from src.runtime.symbiosis_store import submit_feedback, growth_profile
    await submit_feedback("tA", "alice", "praise", "很好用", anonymous=True)
    gp = growth_profile("tA")
    assert gp["tenant_id"] == "tA"
    assert "days_active" in gp
    assert "current_circle" in gp
    assert "unlocked_agents" in gp
    assert "total_agents" in gp
    assert gp["feedback_contributed"] >= 1
    assert gp["ideas_adopted"] == 0  # 未 released


# ---------------- API 集成（auth override + tenant contextvar） ----------------

@pytest.fixture
def app():
    from fastapi import FastAPI
    from src.runtime.api import env_perception
    from src.runtime.authn.deps import require_auth
    from src.runtime.context import set_current_tenant
    import src.runtime.api.env_perception as ep

    application = FastAPI()
    application.include_router(ep.router)
    return application


@pytest.mark.asyncio
async def test_api_feedback_endpoints(app, monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from src.runtime.authn.deps import require_auth
    from src.runtime.context import set_current_tenant
    from src.runtime.api import env_perception as ep

    app.dependency_overrides[require_auth] = lambda: {
        "tenant_id": "tA",
        "role": "TENANT_ADMIN",
        "username": "alice",
    }
    set_current_tenant("tA")

    t = ASGITransport(app=app)
    async with AsyncClient(transport=t, base_url="http://t") as c:
        # 提交反馈
        r = await c.post(
            "/environment/feedback",
            json={"kind": "idea", "text": "想要更细的供应商画像", "anonymous": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tracking_id"].startswith("fb_")
        assert body["status"] == "submitted"

        # 状态端点
        st = await c.get("/environment/feedback/status")
        assert st.status_code == 200
        assert st.json()["total"] >= 1

        # 成长档案
        gp = await c.get("/environment/growth-profile")
        assert gp.status_code == 200
        assert gp.json()["tenant_id"] == "tA"

        # 进化回告（暂无 released）
        ev = await c.get("/environment/evolution")
        assert ev.status_code == 200
        assert ev.json()["notifications"] == []


@pytest.mark.asyncio
async def test_api_isolation_via_context(app, monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from src.runtime.authn.deps import require_auth
    from src.runtime.context import set_current_tenant
    from src.runtime.api import env_perception as ep

    # 租户 B（无反馈）
    app.dependency_overrides[require_auth] = lambda: {
        "tenant_id": "tB",
        "role": "TENANT_ADMIN",
        "username": "bob",
    }
    set_current_tenant("tB")
    t = ASGITransport(app=app)
    async with AsyncClient(transport=t, base_url="http://t") as c:
        st = await c.get("/environment/feedback/status")
        assert st.json()["total"] == 0  # 🔴 B 看不到 A 的反馈
        gp = await c.get("/environment/growth-profile")
        assert gp.json()["feedback_contributed"] == 0
