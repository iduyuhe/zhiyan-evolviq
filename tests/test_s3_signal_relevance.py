"""S3-2 相关性打分降噪专项测试（#317）

覆盖：
1. derive_attention：订阅/画像 → 关注类目权重 + 关注实体集
2. score_signal：类目命中 / 未关注降噪 / 官方保底 / 实体命中 / 目标 agent / F4 透明 reason
3. rank_intelligence_signals：降噪过滤 + 相关性降序 + suppressed_count
4. tenant_feed 集成：relevance 字段落地 + suppressed_count（override auth）
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.runtime.uns import uns, CRED_OFFICIAL, CRED_GENERAL
from src.runtime.api.env_perception import router
from src.runtime.signal_relevance import (
    CATEGORY_AGENT_MAP,
    derive_attention,
    rank_intelligence_signals,
    score_signal,
)


def _sig(category, credibility, entities=None, payload=None):
    return {
        "id": f"{category}-{credibility}",
        "source": f"env://test/{category}",
        "credibility": credibility,
        "payload": {"title": f"{category} signal", "category": category, **(payload or {})},
        "entities": entities or [],
    }


# ============ 1. derive_attention ============


class TestDeriveAttention:
    def test_subscription_to_category_weight(self):
        subs = [{"source_name": "policy", "enabled": True}]
        att = derive_attention(None, subs)
        assert att["category_weights"].get("policy") == 0.5
        assert "policy" in CATEGORY_AGENT_MAP  # 映射表健全

    def test_profile_top_objects_to_entities(self):
        profile = {"top_objects": [{"object": "MAT:铜"}, {"object": "VENDOR:宝武"}], "event_types": {}}
        att = derive_attention(profile, [])
        assert "铜" in att["entities"]
        assert "宝武" in att["entities"]

    def test_empty_input_neutral(self):
        att = derive_attention(None, None)
        assert att["category_weights"] == {}
        assert att["entities"] == set()


# ============ 2. score_signal ============


class TestScoreSignal:
    def test_category_hit_high_score(self):
        att = {"category_weights": {"policy": 0.5}, "entities": set()}
        r = score_signal(_sig("policy", CRED_GENERAL), att)
        assert r["score"] >= 0.5
        assert not r["suppressed"]
        assert "compliance_q" in r["target_agents"]

    def test_unfocused_low_general_suppressed(self):
        att = {"category_weights": {"policy": 0.5}, "entities": set()}
        r = score_signal(_sig("unknown_cat", CRED_GENERAL), att)
        assert r["score"] < 0.25
        assert r["suppressed"] is True

    def test_official_floor_not_suppressed(self):
        att = {"category_weights": {}, "entities": set()}
        r = score_signal(_sig("unknown_cat", CRED_OFFICIAL), att)
        assert r["score"] >= 0.4
        assert r["suppressed"] is False

    def test_entity_hit_bonus(self):
        att = {"category_weights": {}, "entities": {"铜"}}
        r = score_signal(_sig("market", CRED_GENERAL, entities=["MAT:铜"]), att)
        assert r["score"] >= 0.35
        assert "涉及你关注的实体" in r["reason"]

    def test_neutral_baseline_no_suppress(self):
        att = {"category_weights": {}, "entities": set()}
        r = score_signal(_sig("benchmark", CRED_GENERAL), att)
        assert r["score"] == 0.5
        assert not r["suppressed"]

    def test_reason_transparent(self):
        att = {"category_weights": {"policy": 0.5}, "entities": set()}
        r = score_signal(_sig("policy", CRED_GENERAL), att)
        assert "命中你关注的类目" in r["reason"]
        assert "credibility=general" in r["reason"]


# ============ 3. rank_intelligence_signals ============


class TestRankSignals:
    def test_suppress_and_count(self):
        att = {"category_weights": {"policy": 0.5}, "entities": set()}
        sigs = [_sig("policy", CRED_GENERAL), _sig("unknown_cat", CRED_GENERAL)]
        ranked, suppressed = rank_intelligence_signals(sigs, att)
        assert suppressed == 1
        assert len(ranked) == 1
        assert ranked[0]["relevance"]["category"] == "policy"
        assert ranked[0]["kind"] == "intelligence"

    def test_sorted_by_score_desc(self):
        att = {"category_weights": {"policy": 0.5, "market": 0.5}, "entities": set()}
        sigs = [_sig("market", CRED_GENERAL), _sig("policy", CRED_OFFICIAL)]
        ranked, _ = rank_intelligence_signals(sigs, att)
        assert ranked[0]["relevance"]["score"] >= ranked[-1]["relevance"]["score"]

    def test_include_suppressed(self):
        att = {"category_weights": {"policy": 0.5}, "entities": set()}
        sigs = [_sig("unknown_cat", CRED_GENERAL)]
        ranked, suppressed = rank_intelligence_signals(sigs, att, include_suppressed=True)
        assert suppressed == 0
        assert len(ranked) == 1
        assert ranked[0]["relevance"]["suppressed"] is True


# ============ 4. tenant_feed 集成 ============


@pytest.fixture
def feed_app():
    app = FastAPI()
    app.include_router(router)
    from src.runtime.authn.deps import require_auth
    from src.runtime.context import get_current_tenant

    app.dependency_overrides[require_auth] = lambda: {
        "tenant_id": "default",
        "role": "TENANT_ADMIN",
        "username": "tester",
    }
    app.dependency_overrides[get_current_tenant] = lambda: "default"
    return app


class TestFeedIntegration:
    @pytest.mark.asyncio
    async def test_feed_returns_relevance_and_suppressed_count(self, feed_app):
        uns._events.clear()
        # policy official（命中关注，高相关）+ benchmark general（命中关注）+ unknown（降噪）
        uns.publish_environment(
            "env://test/policy",
            {"title": "政策信号", "category": "policy"},
            entities=["POLICY:x"],
            credibility=CRED_OFFICIAL,
        )
        uns.publish_environment(
            "env://test/market",
            {"title": "行情信号", "category": "market"},
            credibility=CRED_GENERAL,
        )
        # 借 policy 源名通过订阅过滤，但类目=competitor 非本租户关注 → S3-2 降噪
        uns.publish_environment(
            "env://test/policy",
            {"title": "竞品杂讯", "category": "competitor"},
            credibility=CRED_GENERAL,
        )

        transport = ASGITransport(app=feed_app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.get("/environment/feed?n=20")
        assert resp.status_code == 200
        data = resp.json()

        intel = [s for s in data["signals"] if s.get("kind") == "intelligence"]
        assert len(intel) >= 2
        # 每条 intelligence 必带 relevance（score / target_agents / reason）
        for s in intel:
            assert "relevance" in s
            assert "score" in s["relevance"]
            assert "target_agents" in s["relevance"]
            assert "reason" in s["relevance"]
        # unknown_cat 被降噪 → suppressed_count >= 1
        assert data["suppressed_count"] >= 1
        # 高相关（policy official）应排在前列
        assert intel[0]["relevance"]["score"] >= 0.4
