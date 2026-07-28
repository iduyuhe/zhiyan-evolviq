"""S3-3 源推荐专项测试（#317，γ1）

覆盖：
1. build_tenant_interest：行为画像(agent) → 类目兴趣 / BOM 物料 → 类目 + 透明证据 / 行业 → 默认类目
2. recommend_sources：推荐度打分 + F4 透明 reasons + 已订阅标记 + 按推荐度降序
3. /environment/source-recommendations 集成：聚合本租户画像/BOM/行业 + 透明推荐落地

🔴 隐私红线：所有输入均为本租户数据；纯函数无跨租户副作用。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.runtime.source_recommendation import (
    build_tenant_interest,
    recommend_sources,
)
from src.runtime.api.env_perception import router


# ============ 1. build_tenant_interest ============


class TestBuildTenantInterest:
    def test_agent_usage_to_category(self):
        # procurement_manage 在 CATEGORY_AGENT_MAP 中服务 market 类目
        profile = {"top_objects": [{"object": "agent:procurement_manage", "count": 5}],
                   "event_types": {}}
        interest = build_tenant_interest(profile, [], None)
        assert interest["category_interests"].get("market", 0) >= 0.7
        assert "procurement_manage" in interest["agent_by_category"].get("market", [])

    def test_bom_material_to_category(self):
        # “8英寸抛光硅片”含“硅” → market；“危化品”含“危化” → policy
        interest = build_tenant_interest(None, ["8英寸抛光硅片", "危化品仓储"], None)
        assert interest["category_interests"].get("market", 0) >= 0.7
        assert interest["category_interests"].get("policy", 0) >= 0.7
        assert "8英寸抛光硅片" in interest["material_by_category"].get("market", [])
        assert "危化品仓储" in interest["material_by_category"].get("policy", [])

    def test_industry_to_default_categories(self):
        interest = build_tenant_interest(None, [], "半导体制造")
        # 半导体 → market+benchmark；制造 → 三类全
        assert "market" in interest["industry_categories"]
        assert "policy" in interest["industry_categories"]
        assert "benchmark" in interest["industry_categories"]

    def test_no_industry_generic_baseline(self):
        interest = build_tenant_interest(None, [], None)
        # 无行业 → 三类通用基线（不遗漏任何官方源）
        for cat in ("policy", "market", "benchmark"):
            assert interest["category_interests"].get(cat, 0) >= 0.5

    def test_empty_input_safe(self):
        interest = build_tenant_interest(None, None, None)
        assert interest["category_interests"]
        assert interest["material_terms"] == set()


# ============ 2. recommend_sources ============


def _known():
    return [
        {"name": "policy", "kind": "policy", "label": "政策法规", "credibility": "official"},
        {"name": "market", "kind": "market", "label": "原材料行情", "credibility": "official"},
        {"name": "benchmark", "kind": "benchmark", "label": "行业对标", "credibility": "official"},
    ]


class TestRecommendSources:
    def test_score_and_reasons_transparent(self):
        profile = {"top_objects": [{"object": "agent:procurement_manage", "count": 5}],
                   "event_types": {}}
        interest = build_tenant_interest(profile, ["8英寸抛光硅片"], "半导体制造")
        recs = recommend_sources(_known(), [], interest)
        assert len(recs) == 3
        market = next(r for r in recs if r["source_name"] == "market")
        # market 同时被 BOM 硅片 + agent + 行业命中 → 高分
        assert market["score"] >= 0.7
        assert any("BOM" in r for r in market["reasons"]) or any("智能体" in r for r in market["reasons"])
        # F4 透明：reasons 非空且为字符串
        assert all(isinstance(r, str) for r in market["reasons"])

    def test_subscribed_flag_and_default(self):
        subs = [
            {"source_name": "policy", "enabled": True, "is_default": False},
            {"source_name": "market", "enabled": False, "is_default": True},
            {"source_name": "benchmark", "enabled": True, "is_default": True},
        ]
        interest = build_tenant_interest(None, [], "制造")
        recs = recommend_sources(_known(), subs, interest)
        by_name = {r["source_name"]: r for r in recs}
        assert by_name["policy"]["subscribed"] is True
        assert by_name["policy"]["is_default"] is False
        assert by_name["market"]["subscribed"] is False
        assert by_name["benchmark"]["subscribed"] is True

    def test_sorted_by_score_desc(self):
        profile = {"top_objects": [{"object": "agent:procurement_manage", "count": 5}],
                   "event_types": {}}
        interest = build_tenant_interest(profile, ["铜箔"], "电子制造")
        recs = recommend_sources(_known(), [], interest)
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_only_mapped_sources(self):
        # 未知源名（不在 SOURCE_NAME_CATEGORY）不进入推荐
        known = _known() + [{"name": "social", "kind": "social", "label": "社媒", "credibility": "general"}]
        interest = build_tenant_interest(None, [], "制造")
        recs = recommend_sources(known, [], interest)
        assert all(r["source_name"] in ("policy", "market", "benchmark") for r in recs)


# ============ 3. API 集成 ============


@pytest.fixture
def rec_app(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    from src.runtime.authn.deps import require_auth
    from src.runtime.context import get_current_tenant
    from src.runtime.behavior_store import behavior_store
    from src.runtime.bom_store import bom_store

    app.dependency_overrides[require_auth] = lambda: {
        "tenant_id": "default", "role": "TENANT_ADMIN", "username": "tester",
    }
    app.dependency_overrides[get_current_tenant] = lambda: "default"

    # 本租户画像：常用 procurement_manage（→ market）
    monkeypatch.setattr(
        behavior_store, "profile",
        lambda tenant, days=30: {
            "tenant_id": tenant, "window_days": days, "total_events": 10,
            "event_types": {"agent_session": 10},
            "top_objects": [{"object": "agent:procurement_manage", "count": 10}],
            "active_users": 1, "events_last_7d": 10, "generated_at": "",
        },
    )
    # 本租户 BOM：含硅片（→ market）+ 危化品（→ policy）
    monkeypatch.setattr(bom_store, "list_for", lambda tenant: [{"id": "b1"}])
    monkeypatch.setattr(bom_store, "get", lambda tenant, bid: {
        "id": bid, "items": [{"material": "8英寸抛光硅片"}, {"material": "危化品仓储"}],
    })
    # 行业变量
    monkeypatch.setenv("ZHIYAN_INDUSTRY", "半导体制造")
    return app


class TestSourceRecommendationsAPI:
    @pytest.mark.asyncio
    async def test_endpoint_returns_transparent_recs(self, rec_app):
        transport = ASGITransport(app=rec_app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.get("/environment/source-recommendations")
        assert resp.status_code == 200
        data = resp.json()

        assert data["tenant_id"] == "default"
        assert data["industry"] == "半导体制造"
        # interest 透明证据落地
        assert "market" in data["interest"]["category_interests"]
        assert "8英寸抛光硅片" in data["interest"]["material_terms"]
        # 推荐列表：三官方源齐全 + 透明理由 + 按推荐度降序
        recs = data["recommendations"]
        assert {r["source_name"] for r in recs} == {"policy", "market", "benchmark"}
        for r in recs:
            assert "score" in r and "reasons" in r
            assert isinstance(r["reasons"], list) and len(r["reasons"]) > 0
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)
        # market 同时被 BOM 硅片 + agent + 行业命中 → 应排首位或高分
        market = next(r for r in recs if r["source_name"] == "market")
        assert market["score"] >= 0.7
