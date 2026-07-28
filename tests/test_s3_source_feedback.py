"""S3-4 采纳/驳回反哺专项测试（#318，与蓝弧后果回流同构）

覆盖：
1. recommendation_feedback_store.record + adjustments_for：采纳加分类目 boost / 驳回压源&类目 /
   最新动作胜出 / 🔴 租户隔离。
2. source_recommendation.apply_feedback：驳回下调到 REJECT_FLOOR + F4 透明理由 / 采纳上调 + flag。
3. API 集成：POST /environment/recommendations/feedback → GET /environment/source-recommendations 体现调整。

🔴 隐私红线：仅本租户反馈参与本租户推荐；adjustments_for 严格按 tenant 过滤，绝不跨租户。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.runtime.recommendation_feedback_store import (
    FB_ADOPT,
    FB_REJECT,
    adjustments_for,
    record as fb_record,
)
from src.runtime.source_recommendation import apply_feedback, recommend_sources
from src.runtime.api.env_perception import router
from src.runtime.behavior_store import behavior_store


@pytest.fixture(autouse=True)
def clear_behavior_memory():
    """每个测试前清空行为事件内存（避免跨测试污染反馈聚合）。"""
    behavior_store.clear_memory()
    yield
    behavior_store.clear_memory()


# ============ 1. recommendation_feedback_store ============


class TestFeedbackStore:
    @pytest.mark.asyncio
    async def test_adopt_boosts_category(self):
        await fb_record("default", "source", "market", FB_ADOPT, "market")
        adj = adjustments_for("default")
        assert adj["category_boost"].get("market") == 0.15
        assert adj["count"] == 1
        assert adj["rejected_sources"] == []

    @pytest.mark.asyncio
    async def test_reject_dampens_source_and_category(self):
        await fb_record("default", "source", "benchmark", FB_REJECT, "benchmark")
        adj = adjustments_for("default")
        assert "benchmark" in adj["rejected_sources"]
        assert "benchmark" in adj["rejected_categories"]
        assert adj["count"] == 1

    @pytest.mark.asyncio
    async def test_latest_action_wins(self):
        # 同一源先采纳后驳回 → 驳回胜出
        await fb_record("default", "source", "market", FB_ADOPT, "market")
        await fb_record("default", "source", "market", FB_REJECT, "market")
        adj = adjustments_for("default")
        assert "market" in adj["rejected_sources"]
        assert "market" not in adj["category_boost"]

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        await fb_record("tenantA", "source", "market", FB_ADOPT, "market")
        # tenantB 不应看到 tenantA 的反馈
        adj_b = adjustments_for("tenantB")
        assert adj_b["count"] == 0
        assert adj_b["category_boost"] == {}
        # tenantA 自身可见
        adj_a = adjustments_for("tenantA")
        assert adj_a["category_boost"].get("market") == 0.15


# ============ 2. apply_feedback ============


def _recs():
    return [
        {"source_name": "policy", "category": "policy", "score": 0.6, "reasons": ["通用环境信息源"]},
        {"source_name": "market", "category": "market", "score": 0.6, "reasons": ["通用环境信息源"]},
        {"source_name": "benchmark", "category": "benchmark", "score": 0.6, "reasons": ["通用环境信息源"]},
    ]


class TestApplyFeedback:
    def test_reject_lowers_score_and_flags(self):
        adj = {"category_boost": {}, "rejected_sources": ["benchmark"], "rejected_categories": [], "count": 1}
        out, applied = apply_feedback(_recs(), adj)
        assert applied is True
        bench = next(r for r in out if r["source_name"] == "benchmark")
        assert bench["rejected"] is True
        assert bench["score"] <= 0.12
        assert any("驳回" in r for r in bench["reasons"])

    def test_adopt_boosts_category_score(self):
        adj = {"category_boost": {"market": 0.15}, "rejected_sources": [], "rejected_categories": [], "count": 1}
        out, applied = apply_feedback(_recs(), adj)
        assert applied is True
        market = next(r for r in out if r["source_name"] == "market")
        assert market["score"] == min(1.0, round(0.6 + 0.15, 3))
        assert any("上调" in r for r in market["reasons"])

    def test_no_feedback_no_change(self):
        adj = {"category_boost": {}, "rejected_sources": [], "rejected_categories": [], "count": 0}
        out, applied = apply_feedback(_recs(), adj)
        assert applied is False
        assert all(not r.get("rejected") for r in out)

    def test_result_sorted_by_score_desc(self):
        adj = {"category_boost": {"market": 0.3}, "rejected_sources": ["benchmark"], "rejected_categories": [], "count": 2}
        out, _ = apply_feedback(_recs(), adj)
        scores = [r["score"] for r in out]
        assert scores == sorted(scores, reverse=True)
        # 被驳回的 benchmark 应排到末位
        assert out[-1]["source_name"] == "benchmark"


# ============ 3. API 集成 ============


@pytest.fixture
def fb_app(monkeypatch):
    """租户 default 的源推荐 + 反馈集成环境（含画像/BOM/行业 mock）。"""
    app = FastAPI()
    app.include_router(router)
    from src.runtime.authn.deps import require_auth
    from src.runtime.context import get_current_tenant
    from src.runtime.bom_store import bom_store

    app.dependency_overrides[require_auth] = lambda: {
        "tenant_id": "default", "role": "TENANT_ADMIN", "username": "tester",
    }
    app.dependency_overrides[get_current_tenant] = lambda: "default"

    # 画像/BOM/行业：直接走 source_recommendations 端点所需依赖
    # 端点内局部 import behavior_store，故此处直接 monkeypatch 真实模块的方法
    from src.runtime.behavior_store import behavior_store as bs
    monkeypatch.setattr(
        bs, "profile",
        lambda tenant, days=30: {
            "tenant_id": tenant, "window_days": days, "total_events": 1,
            "event_types": {}, "top_objects": [], "active_users": 1,
            "events_last_7d": 1, "generated_at": "",
        },
    )
    import src.runtime.bom_store as bms
    monkeypatch.setattr(bms.bom_store, "list_for", lambda tenant: [])
    monkeypatch.setattr(bms.bom_store, "get", lambda tenant, bid: {"id": bid, "items": []})
    monkeypatch.setenv("ZHIYAN_INDUSTRY", "制造")
    return app


class TestFeedbackAPI:
    @pytest.mark.asyncio
    async def test_post_feedback_reject_then_recs_reflect(self, fb_app):
        transport = ASGITransport(app=fb_app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            # 先驳回 benchmark
            r1 = await c.post(
                "/environment/recommendations/feedback",
                json={"source_name": "benchmark", "action": "reject", "target_kind": "source"},
            )
            assert r1.status_code == 200
            body = r1.json()
            assert body["action"] == "reject"
            assert body["category"] == "benchmark"
            assert "benchmark" in body["adjustments_summary"]["rejected_sources"]

            # 拉取推荐：benchmark 应被标记 rejected 且分数压低
            r2 = await c.get("/environment/source-recommendations")
            assert r2.status_code == 200
            data = r2.json()
            assert data["feedback_applied"] is True
            assert data["feedback_count"] >= 1
            bench = next(x for x in data["recommendations"] if x["source_name"] == "benchmark")
            assert bench["rejected"] is True
            assert bench["score"] <= 0.12

    @pytest.mark.asyncio
    async def test_post_feedback_unknown_source_404(self, fb_app):
        transport = ASGITransport(app=fb_app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post(
                "/environment/recommendations/feedback",
                json={"source_name": "nope", "action": "adopt", "target_kind": "source"},
            )
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_isolation_via_api(self, monkeypatch):
        """两个租户各自反馈，互不可见（A 驳回的不影响 B 的推荐）。

        🔴 端点直接调用 get_current_tenant()（读 contextvar，默认 default），
        故测试用 set_current_tenant 钉死租户上下文（与生产中 require_auth 钉租户同构）。
        """
        import src.runtime.context as ctx
        from src.runtime.authn.deps import require_auth
        from src.runtime.behavior_store import behavior_store as bs
        from src.runtime.bom_store import bom_store as bms

        monkeypatch.setattr(bs, "profile", lambda tenant, days=30: {
            "tenant_id": tenant, "window_days": days, "total_events": 1, "event_types": {},
            "top_objects": [], "active_users": 1, "events_last_7d": 1, "generated_at": "",
        })
        monkeypatch.setattr(bms, "list_for", lambda tenant: [])
        monkeypatch.setattr(bms, "get", lambda tenant, bid: {"id": bid, "items": []})
        monkeypatch.setenv("ZHIYAN_INDUSTRY", "制造")

        appA = FastAPI(); appA.include_router(router)
        appA.dependency_overrides[require_auth] = lambda: {"tenant_id": "A", "role": "TENANT_ADMIN", "username": "a"}
        appB = FastAPI(); appB.include_router(router)
        appB.dependency_overrides[require_auth] = lambda: {"tenant_id": "B", "role": "TENANT_ADMIN", "username": "b"}

        tA = ASGITransport(app=appA)
        tB = ASGITransport(app=appB)
        async with AsyncClient(transport=tA, base_url="http://a") as cA, AsyncClient(transport=tB, base_url="http://b") as cB:
            ctx.set_current_tenant("A")
            await cA.post(
                "/environment/recommendations/feedback",
                json={"source_name": "benchmark", "action": "reject", "target_kind": "source"},
            )
            ra = (await cA.get("/environment/source-recommendations")).json()
            ctx.set_current_tenant("B")
            rb = (await cB.get("/environment/source-recommendations")).json()

        bench_a = next(x for x in ra["recommendations"] if x["source_name"] == "benchmark")
        bench_b = next(x for x in rb["recommendations"] if x["source_name"] == "benchmark")
        assert bench_a["rejected"] is True       # A 的反馈生效
        assert bench_b["rejected"] is False      # B 不受 A 影响（🔴 隔离）
        assert rb["feedback_count"] == 0
