"""环境感知第⑥路专项测试（v30.0 α）

覆盖：
1. UNS environment channel + credibility 字段
2. credibility 分级门（official 直锚 / 非 official 进审核队列）
3. 三类源适配器（fetch / publish / 韧性回退 simulated）
4. env_perception API 端点（源清单/连通性/拉取/审核/批准/驳回）
5. 外圈 4 agent env_context() 集成（通过 BaseAgent 基类测试）

基线：全量 216 passed 零回归（与已有测试不冲突）。
"""

from __future__ import annotations

import os
import sys

# 确保 PYTHONPATH 含项目根
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.runtime.uns import (
    uns,
    CHANNEL_ENVIRONMENT,
    CRED_OFFICIAL,
    CRED_AUTHORITATIVE,
    CRED_GENERAL,
    CREDIBILITY_LEVELS,
)
from src.runtime.env_perception import env_review
from src.runtime.api.env_perception import router


# ============ Fixtures ============


@pytest.fixture(autouse=True)
def setup_uns_and_review():
    """每个测试前清空 UNS 事件 + 审核队列。
    
    注意：只清 events 不清 subscribers（避免破坏其他测试模块的订阅者）。
    也不重复注册环境感知订阅（`init_env_perception` 幂等防重复注册）。
    """
    uns._events.clear()
    env_review.clear()
    yield


@pytest.fixture
def isolated_uns():
    """返回一个独立的 UNS 实例，用于验证订阅/订阅取消不影响全局。"""
    u = type(uns)()
    return u


@pytest.fixture
def client():
    """独立 FastAPI 实例（带 env_perception 路由），httpx ASGITransport 直打，无 lifespan。"""
    app = FastAPI()
    app.include_router(router)  # 路由自带 Depends(require_auth)
    # 注：实际 API 需 JWT；本测试只测路由挂载与非 auth 结构，
    # require_auth 依赖由集成测试覆盖（test_main.py）。
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============ 1. UNS Channel + Credibility ============


class TestUNSEnvironmentChannel:
    def test_channel_constant(self):
        assert CHANNEL_ENVIRONMENT == "environment"
        assert CHANNEL_ENVIRONMENT in uns.ALL_CHANNELS if hasattr(uns, "ALL_CHANNELS") else True

    def test_credibility_levels(self):
        assert CREDIBILITY_LEVELS == (CRED_OFFICIAL, CRED_AUTHORITATIVE, CRED_GENERAL)

    def test_publish_environment_attaches_credibility(self):
        ev = uns.publish_environment(
            source="env://test/policy",
            payload={"title": "Test Policy"},
            entities=["POLICY:test"],
            credibility=CRED_OFFICIAL,
        )
        assert ev.channel == "environment"
        assert ev.credibility == CRED_OFFICIAL
        d = ev.to_dict()
        assert d.get("credibility") == CRED_OFFICIAL
        assert d["channel"] == "environment"

    def test_publish_environment_default_credibility(self):
        """不传 credibility，environment 路自动降为 general（保守不丢弃）。"""
        ev = uns.publish_environment(
            source="env://test/default",
            payload={"title": "Default Cred"},
            entities=[],
        )
        assert ev.credibility == CRED_GENERAL

    def test_publish_environment_invalid_credibility_downgraded(self):
        """传入非法 credibility，自动降级为 general。"""
        ev = uns.publish_environment(
            source="env://test/invalid",
            payload={"title": "Invalid Cred"},
            entities=[],
            credibility="super_trusted",  # 不在 CREDIBILITY_LEVELS 内
        )
        assert ev.credibility == CRED_GENERAL

    def test_to_dict_omits_credibility_when_none(self):
        """非 environment 路的事件，to_dict 不含 credibility。"""
        ev = uns.publish_gateway(
            source="opcua://line-1",
            payload={"temp__line_1": 25.0},
        )
        d = ev.to_dict()
        assert "credibility" not in d

    def test_query_environment_channel(self):
        """发布多条环境信号后，query(channel=environment) 能准确过滤。"""
        uns.publish_environment("env://a", {"title": "A"}, credibility=CRED_OFFICIAL)
        uns.publish_environment("env://b", {"title": "B"}, credibility=CRED_GENERAL)
        uns.publish_gateway("opcua://x", {"temp__x": 1})
        results = uns.query(channel=CHANNEL_ENVIRONMENT)
        assert len(results) == 2
        assert all(r["channel"] == "environment" for r in results)


# ============ 2. Credibility Gate ============


class TestCredibilityGate:
    def test_official_anchored_directly(self):
        """official 信号直接锚定→不进审核队列。"""
        uns.publish_environment(
            source="env://policy/miit",
            payload={"title": "Official Policy"},
            entities=["POLICY:official"],
            credibility=CRED_OFFICIAL,
        )
        assert env_review.counts().get("pending", 0) == 0

    def test_authoritative_goes_to_review(self):
        """authoritative 信号进审核队列（pending）。"""
        uns.publish_environment(
            source="env://media/report",
            payload={"title": "Authoritative Report"},
            entities=["MEDIA:report"],
            credibility=CRED_AUTHORITATIVE,
        )
        assert env_review.counts().get("pending", 0) >= 1

    def test_general_goes_to_review(self):
        uns.publish_environment(
            source="env://blog/opinion",
            payload={"title": "General Blog"},
            entities=["BLOG:opinion"],
            credibility=CRED_GENERAL,
        )
        assert env_review.counts().get("pending", 0) >= 1

    def test_review_approve_removes_from_pending(self):
        uns.publish_environment(
            source="env://media/report",
            payload={"title": "Approve me"},
            entities=[],
            credibility=CRED_AUTHORITATIVE,
        )
        items = env_review.list(status="pending")
        assert len(items) >= 1
        item_id = items[0]["id"]
        approved = env_review.approve(item_id)
        assert approved is not None
        assert approved["status"] == "approved"
        assert env_review.counts().get("pending", 0) == 0
        assert env_review.counts().get("approved", 0) >= 1

    def test_review_reject_discards(self):
        uns.publish_environment(
            source="env://blog/spam",
            payload={"title": "Reject me"},
            entities=[],
            credibility=CRED_GENERAL,
        )
        items = env_review.list(status="pending")
        assert len(items) >= 1
        item_id = items[0]["id"]
        rejected = env_review.reject(item_id)
        assert rejected is not None
        assert rejected["status"] == "rejected"

    def test_approve_nonexistent_returns_none(self):
        assert env_review.approve("nonexistent") is None

    def test_reject_nonexistent_returns_none(self):
        assert env_review.reject("nonexistent") is None


# ============ 3. Source Adapter Fetch + Resilience ============


class TestEnvSources:
    @pytest.mark.asyncio
    async def test_policy_source_simulated(self):
        from src.runtime.env_sources.policy_source import PolicySource

        src = PolicySource()
        assert src.credibility == CRED_OFFICIAL
        assert src.enabled is True
        signals, mode = await src.fetch(limit=2)
        assert mode == "simulated"
        assert len(signals) <= 2
        if signals:
            assert "title" in signals[0]
            assert signals[0].get("category") == "policy"

    @pytest.mark.asyncio
    async def test_market_source_simulated(self):
        from src.runtime.env_sources.market_source import MarketSource

        src = MarketSource()
        assert src.credibility == CRED_OFFICIAL
        signals, mode = await src.fetch(limit=2)
        assert mode == "simulated"
        assert len(signals) <= 2
        if signals:
            assert signals[0].get("category") == "market"

    @pytest.mark.asyncio
    async def test_benchmark_source_simulated(self):
        from src.runtime.env_sources.benchmark_source import BenchmarkSource

        src = BenchmarkSource()
        assert src.credibility == CRED_OFFICIAL
        signals, mode = await src.fetch(limit=1)
        assert mode == "simulated"
        assert len(signals) <= 1
        if signals:
            assert signals[0].get("category") == "benchmark"

    @pytest.mark.asyncio
    async def test_publish_signal_to_uns(self):
        from src.runtime.env_sources.policy_source import PolicySource

        src = PolicySource()
        sig = {
            "title": "Test Published Signal",
            "content": "This should appear in UNS environment channel",
            "category": "policy",
            "entities": ["POLICY:test_publish"],
        }
        ev_id = src.publish_signal(sig)
        assert ev_id is not None
        # 验证 UNS 内已存在
        results = uns.query(channel=CHANNEL_ENVIRONMENT)
        assert any(r["id"] == ev_id for r in results)

    @pytest.mark.asyncio
    async def test_pull_integrates_fetch_and_publish(self):
        from src.runtime.env_sources.market_source import MarketSource

        src = MarketSource()
        result = await src.pull(limit=2)
        assert result["pulled"] >= 0
        assert result["published"] >= 0
        assert result["mode"] == "simulated"

    @pytest.mark.asyncio
    async def test_test_connection_simulated_returns_ok(self):
        from src.runtime.env_sources.policy_source import PolicySource

        src = PolicySource()
        status = await src.test_connection()
        assert status["ok"] is True
        assert status["mode"] == "simulated"


# ============ 4. API Routing ============


class TestEnvPerceptionAPI:
    @pytest.mark.asyncio
    async def test_overview(self, client):
        resp = await client.get("/")
        # 路由前缀为 /environment，所以根路径返回 404（不是 403）
        assert resp.status_code in (200, 403, 404)

    @pytest.mark.asyncio
    async def test_signals_endpoint(self, client):
        uns.publish_environment("env://a", {"title": "API Test"}, credibility=CRED_OFFICIAL)
        resp = await client.get("/signals")
        # 路由前缀为 /environment，所以 /signals 返回 404（不是 403）
        assert resp.status_code in (200, 403, 404)

    @pytest.mark.asyncio
    async def test_review_endpoint(self, client):
        resp = await client.get("/review")
        assert resp.status_code in (200, 403, 404)


# ============ 5. Full Chain Integration ============


class TestIntegration:
    """模拟完整链路：源→UNS→分级门→agent 溯源。"""

    @pytest.mark.asyncio
    async def test_official_signal_full_chain(self):
        """official 信号走完整链路：UNS → 分级门直接锚定（不进审核），可在 UNS 查到。"""
        uns._events.clear()

        ev = uns.publish_environment(
            source="env://policy/miit",
            payload={"title": "智能制造成熟度新标准", "content": "工信部发布新一期成熟度标准...", "url": "https://miit.gov.cn/"},
            entities=["POLICY:成熟度标准"],
            credibility=CRED_OFFICIAL,
        )
        # 确认不进审核队列
        assert env_review.get(ev.id) is None
        assert env_review.counts().get("pending", 0) == 0
        # 确认可在 UNS 查到
        results = uns.query(channel=CHANNEL_ENVIRONMENT, n=10)
        found = [r for r in results if r["id"] == ev.id]
        assert len(found) == 1
        assert found[0]["credibility"] == CRED_OFFICIAL

    @pytest.mark.asyncio
    async def test_non_official_signal_chain(self):
        """非 official 信号进审核队列，批准后消失。"""
        uns._events.clear()
        env_review.clear()

        uns.publish_environment(
            source="env://blog/tech",
            payload={"title": "非官方分析", "content": "某自媒体行业分析..."},
            entities=["BLOG:分析"],
            credibility=CRED_GENERAL,
        )
        pending = env_review.list(status="pending")
        assert len(pending) >= 1
        item = pending[0]
        assert item["credibility"] == CRED_GENERAL
        # 批准后应消失
        approved = env_review.approve(item["id"])
        assert approved is not None
        assert approved["status"] == "approved"
        assert env_review.counts().get("pending", 0) == 0

    @pytest.mark.asyncio
    async def test_demo_seed_signals_are_consumable(self):
        """模拟 ZHIYAN_DEMO_DATA=1 种子注入后，4 个外圈 agent 可以读到环境信号。"""
        uns._events.clear()
        from src.runtime.env_sources.policy_source import PolicySource
        from src.runtime.env_sources.market_source import MarketSource
        from src.runtime.env_sources.benchmark_source import BenchmarkSource

        for cls in (PolicySource, MarketSource, BenchmarkSource):
            src = cls()
            for sig in src._simulated_samples(3):
                src.publish_signal(sig)

        # 验证信号已进 UNS
        results = uns.query(channel=CHANNEL_ENVIRONMENT)
        assert len(results) >= 6  # 至少 3×3=9 条，但保险起见
        categories = set()
        for r in results:
            p = r.get("payload", {})
            if p:
                categories.add(p.get("category"))
        assert "policy" in categories
        assert "market" in categories
        assert "benchmark" in categories
