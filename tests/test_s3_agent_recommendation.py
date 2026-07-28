"""S3-5 行为导航④（无感转型导航器，#319）专项测试

覆盖：
1. build_focus：agent 使用 → 类目关注 / 已采纳类目 boost / 无信号基线。
2. recommend_next_agents：outer→推中圈(locked) / inner→空 / 价值句式格式 / 按匹配度降序。
3. recommend_for_tenant：全管线集成（画像+BOM+行业+已采纳 → 关注 → 下一步）。
4. API 集成：GET /environment/agent-recommendations 与 GET /environment/unlock-progress 注入。
5. 🔴 租户隔离：A 的行为不进入 B 的推荐。

🔴 隐私红线：仅本租户行为参与本租户推荐；绝不跨租户聚合到个体可识别粒度。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.runtime.agent_recommendation import (
    build_focus,
    recommend_next_agents,
    recommend_for_tenant,
)
from src.runtime.api.env_perception import router
from src.runtime.behavior_store import behavior_store
from src.runtime.context import set_current_tenant


@pytest.fixture(autouse=True)
def clear_behavior_memory():
    behavior_store.clear_memory()
    yield
    behavior_store.clear_memory()


def _profile_with_agent(agent: str):
    return {
        "tenant_id": "default", "window_days": 30, "total_events": 1,
        "event_types": {}, "top_objects": [{"object": f"agent:{agent}", "count": 5}],
        "active_users": 1, "events_last_7d": 1, "generated_at": "",
    }


# ============ 1. build_focus ============


class TestBuildFocus:
    def test_agent_usage_maps_to_category(self):
        # procurement_manage 服务 market 类目
        focus = build_focus(_profile_with_agent("procurement_manage"), {}, None)
        assert focus["focus_categories"].get("market", 0) >= 0.7
        assert any("procurement_manage" in s for s in focus["signals"])

    def test_adopted_category_boosted(self):
        focus = build_focus({}, {"market": 0.5}, ["market"])
        assert focus["focus_categories"]["market"] > 0.5  # +ADOPT_BOOST
        assert any("已采纳" in s for s in focus["signals"])

    def test_baseline_when_no_signal(self):
        focus = build_focus({}, {}, None)
        # 无信号 → 三类目基线，且明确信号文案
        for cat in ("policy", "market", "benchmark"):
            assert focus["focus_categories"][cat] == 0.3
        assert any("暂无明确行为信号" in s for s in focus["signals"])


# ============ 2. recommend_next_agents ============


class TestRecommendNextAgents:
    def test_outer_recommends_middle_locked(self):
        focus = build_focus(_profile_with_agent("procurement_manage"), {}, None)
        recs = recommend_next_agents("outer", focus)
        assert len(recs) > 0
        assert all(r["locked"] is True for r in recs)
        # 中圈 agent 应出现（cost_analysis/demand_order 服务 market）
        agents = {r["agent"] for r in recs}
        assert "cost_analysis" in agents

    def test_value_sentence_format(self):
        focus = build_focus(_profile_with_agent("procurement_manage"), {}, None)
        recs = recommend_next_agents("outer", focus)
        for r in recs:
            assert r["value_sentence"].startswith("你关注的")
            assert "配合" in r["value_sentence"]
            assert "能算出" in r["value_sentence"]
            # F4 透明：含依据理由
            assert len(r["reasons"]) >= 1
            assert r["source"] == "behavior"

    def test_inner_returns_empty(self):
        focus = build_focus(_profile_with_agent("executive_cockpit"), {}, None)
        assert recommend_next_agents("inner", focus) == []

    def test_sorted_by_match_desc(self):
        # market 强关注 → market 类 agent（cost_analysis/demand_order）应排前
        focus = build_focus(_profile_with_agent("procurement_manage"), {}, None)
        recs = recommend_next_agents("outer", focus, limit=10)
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)
        # 最高分 agent 应是服务 market 的中圈 agent
        assert recs[0]["agent"] in ("cost_analysis", "demand_order")


# ============ 3. recommend_for_tenant 全管线 ============


class TestRecommendForTenant:
    def test_integration_outer_circle(self, monkeypatch):
        monkeypatch.setattr(
            behavior_store, "profile",
            lambda tenant, days=30: _profile_with_agent("procurement_manage"),
        )
        import src.runtime.bom_store as bms
        monkeypatch.setattr(bms.bom_store, "list_for", lambda tenant: [])
        monkeypatch.setattr(bms.bom_store, "get", lambda tenant, bid: {"id": bid, "items": []})
        monkeypatch.setenv("ZHIYAN_INDUSTRY", "制造")
        out = recommend_for_tenant("default")
        assert out["current_circle"] == "outer"
        assert len(out["recommended_next"]) > 0
        assert all(r["locked"] for r in out["recommended_next"])

    def test_inner_circle_no_recommendation(self, monkeypatch):
        # 私有化部署 → inner 圈 → 无下一步
        monkeypatch.setenv("ZHIYAN_PRIVATE_DEPLOYMENT", "1")
        monkeypatch.setattr(
            behavior_store, "profile",
            lambda tenant, days=30: _profile_with_agent("executive_cockpit"),
        )
        import src.runtime.bom_store as bms
        monkeypatch.setattr(bms.bom_store, "list_for", lambda tenant: [])
        monkeypatch.setattr(bms.bom_store, "get", lambda tenant, bid: {"id": bid, "items": []})
        out = recommend_for_tenant("default")
        assert out["current_circle"] == "inner"
        assert out["recommended_next"] == []
        monkeypatch.delenv("ZHIYAN_PRIVATE_DEPLOYMENT", raising=False)


# ============ 4. API 集成 ============


@pytest.fixture
def rec_app(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    from src.runtime.authn.deps import require_auth
    from src.runtime.bom_store import bom_store

    app.dependency_overrides[require_auth] = lambda: {
        "tenant_id": "default", "role": "TENANT_ADMIN", "username": "tester",
    }
    monkeypatch.setattr(
        behavior_store, "profile",
        lambda tenant, days=30: _profile_with_agent("procurement_manage"),
    )
    import src.runtime.bom_store as bms
    monkeypatch.setattr(bms.bom_store, "list_for", lambda tenant: [])
    monkeypatch.setattr(bms.bom_store, "get", lambda tenant, bid: {"id": bid, "items": []})
    monkeypatch.setenv("ZHIYAN_INDUSTRY", "制造")
    return app


class TestAgentRecommendationAPI:
    @pytest.mark.asyncio
    async def test_standalone_endpoint(self, rec_app):
        transport = ASGITransport(app=rec_app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get("/environment/agent-recommendations")
            assert r.status_code == 200
            data = r.json()
            assert data["current_circle"] == "outer"
            assert len(data["recommended_next"]) > 0
            rec = data["recommended_next"][0]
            assert rec["locked"] is True
            assert rec["source"] == "behavior"
            assert "能算出" in rec["value_sentence"]

    @pytest.mark.asyncio
    async def test_unlock_progress_injects_recommended_next(self, rec_app):
        transport = ASGITransport(app=rec_app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.get("/environment/unlock-progress")
            assert r.status_code == 200
            data = r.json()
            assert "recommended_next" in data
            assert len(data["recommended_next"]) > 0


# ============ 5. 🔴 租户隔离 ============


class TestTenantIsolation:
    @pytest.mark.asyncio
    async def test_a_behavior_not_in_b(self, monkeypatch):
        """租户 A 常使用 procurement_manage（market）→ 推中圈 market agent；
        租户 B 无任何行为 → 仅基线推荐，二者推荐应可区分（聚焦不同）。"""
        app = FastAPI()
        app.include_router(router)
        from src.runtime.authn.deps import require_auth

        app.dependency_overrides[require_auth] = lambda: {
            "tenant_id": "A", "role": "TENANT_ADMIN", "username": "a",
        }
        import src.runtime.bom_store as bms
        monkeypatch.setattr(bms.bom_store, "list_for", lambda tenant: [])
        monkeypatch.setattr(bms.bom_store, "get", lambda tenant, bid: {"id": bid, "items": []})

        # A：有 market 类 agent 使用
        prof_a = _profile_with_agent("procurement_manage")
        # B：空画像
        prof_b = {
            "tenant_id": "B", "window_days": 30, "total_events": 0,
            "event_types": {}, "top_objects": [], "active_users": 0,
            "events_last_7d": 0, "generated_at": "",
        }

        def prof_switch(tenant, days=30):
            return prof_a if tenant == "A" else prof_b

        monkeypatch.setattr(behavior_store, "profile", prof_switch)
        monkeypatch.setenv("ZHIYAN_INDUSTRY", "制造")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            set_current_tenant("A")
            data_a = (await c.get("/environment/agent-recommendations")).json()
            set_current_tenant("B")
            data_b = (await c.get("/environment/agent-recommendations")).json()

        # A 的 top 推荐应是 market 类（cost_analysis/demand_order）
        assert data_a["recommended_next"][0]["agent"] in ("cost_analysis", "demand_order")
        # A 有明确信号（基于行为），B 为基线
        a_has_signal = any("procurement_manage" in s for r in data_a["recommended_next"] for s in r["reasons"])
        b_has_signal = any("procurement_manage" in s for r in data_b["recommended_next"] for s in r["reasons"])
        assert a_has_signal is True
        assert b_has_signal is False  # 🔴 B 绝不受 A 行为影响
