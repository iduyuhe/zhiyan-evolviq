"""S2 v30.5 β 专项测试——免费额度计量（#309 S2-1b）

覆盖：
1. 计量器：月解读计数/超限 UsageExceeded；日信号去重+截断；豁免规则
   （default 租户 / gateway_config 非空=信任爬梯③ / ENFORCE 关闸）
2. API：/environment/quota 视图（三维额度）；/environment/feed quota 块
   （截断 + exhausted 提示，不 402）；/sessions 三入口超限 402
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.runtime import usage_meter as um
from src.runtime.usage_meter import (
    METRIC_INSIGHTS,
    METRIC_SIGNALS,
    UsageExceeded,
    UsageMeter,
    usage_meter,
)
from src.runtime.env_subscription_store import env_subscription_store
from src.runtime.uns import uns


TENANT = "t-usage-a"
TENANT_B = "t-usage-b"


# ============ Fixtures ============


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """每个测试前后清空计量单例/订阅单例/UNS；强制 ENFORCE 开。"""
    monkeypatch.setattr(um, "ENFORCE", True)
    usage_meter._counters.clear()
    usage_meter._seen.clear()
    env_subscription_store._by_tenant.clear()
    uns._events.clear()
    yield
    usage_meter._counters.clear()
    usage_meter._seen.clear()
    env_subscription_store._by_tenant.clear()
    uns._events.clear()


def _sig(i: int, cred: str = "official") -> dict:
    return {
        "id": f"sig-{i}",
        "source": "env://policy/policy",
        "channel": "environment",
        "credibility": cred,
        "payload": {"title": f"信号{i}"},
        "entities": [],
    }


# ============ 1. 计量器单元 ============


class TestInsightMeter:
    @pytest.mark.asyncio
    async def test_consume_and_exceed(self, monkeypatch):
        monkeypatch.setattr(um, "FREE_MONTHLY_INSIGHTS", 3)
        m = UsageMeter()
        for _ in range(3):
            await m.consume_insight(TENANT)
        assert m.used(TENANT, METRIC_INSIGHTS) == 3
        with pytest.raises(UsageExceeded) as ei:
            await m.consume_insight(TENANT)
        assert "信任爬梯③" in str(ei.value)

    @pytest.mark.asyncio
    async def test_default_tenant_unlimited(self, monkeypatch):
        monkeypatch.setattr(um, "FREE_MONTHLY_INSIGHTS", 1)
        m = UsageMeter()
        for _ in range(5):
            await m.consume_insight("default")
        assert m.used("default", METRIC_INSIGHTS) == 0  # 豁免不计数

    @pytest.mark.asyncio
    async def test_enforce_off_unlimited(self, monkeypatch):
        monkeypatch.setattr(um, "ENFORCE", False)
        monkeypatch.setattr(um, "FREE_MONTHLY_INSIGHTS", 1)
        m = UsageMeter()
        for _ in range(5):
            await m.consume_insight(TENANT)
        assert m.used(TENANT, METRIC_INSIGHTS) == 0

    @pytest.mark.asyncio
    async def test_gateway_config_paid_unlimited(self, monkeypatch):
        """信任爬梯③：gateway_config 非空 = 已接内部数据源 = 免限额。"""
        monkeypatch.setattr(um, "FREE_MONTHLY_INSIGHTS", 1)
        from src.runtime.tenant_store import tenant_store

        monkeypatch.setattr(
            tenant_store, "get_gateway_config", lambda tid: {"host": "x"} if tid == TENANT else None
        )
        m = UsageMeter()
        for _ in range(5):
            await m.consume_insight(TENANT)  # 不抛
        with pytest.raises(UsageExceeded):
            await m.consume_insight(TENANT_B)
            await m.consume_insight(TENANT_B)


class TestSignalMeter:
    @pytest.mark.asyncio
    async def test_dedupe_same_day(self, monkeypatch):
        monkeypatch.setattr(um, "FREE_DAILY_SIGNALS", 10)
        m = UsageMeter()
        sigs = [_sig(i) for i in range(4)]
        allowed, q = await m.consume_signals(TENANT, sigs)
        assert len(allowed) == 4 and q["used"] == 4
        # 同批重复轮询：不再计数
        allowed2, q2 = await m.consume_signals(TENANT, sigs)
        assert len(allowed2) == 4 and q2["used"] == 4

    @pytest.mark.asyncio
    async def test_truncate_over_limit(self, monkeypatch):
        monkeypatch.setattr(um, "FREE_DAILY_SIGNALS", 5)
        m = UsageMeter()
        allowed, q = await m.consume_signals(TENANT, [_sig(i) for i in range(8)])
        assert len(allowed) == 5
        assert q["truncated"] == 3 and q["exhausted"] is True
        assert "信任爬梯③" in (q["upgrade_hint"] or "")
        # 次日之前继续给新信号：全部截断，但已计过的仍可见
        allowed2, q2 = await m.consume_signals(TENANT, [_sig(i) for i in range(8)] + [_sig(99)])
        assert len(allowed2) == 5 and q2["truncated"] == 4

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, monkeypatch):
        monkeypatch.setattr(um, "FREE_DAILY_SIGNALS", 5)
        m = UsageMeter()
        await m.consume_signals(TENANT, [_sig(i) for i in range(5)])
        allowed_b, q_b = await m.consume_signals(TENANT_B, [_sig(i) for i in range(3)])
        assert len(allowed_b) == 3 and q_b["used"] == 3  # B 不受 A 用量影响


# ============ 2. API 层 ============


@pytest.fixture
def env_client():
    from src.runtime.api.env_perception import router

    app = FastAPI()
    app.include_router(router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def sessions_client():
    from src.runtime.api.sessions import router

    app = FastAPI()
    app.include_router(router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestQuotaApi:
    @pytest.mark.asyncio
    async def test_quota_view_three_metrics(self, env_client):
        async with env_client as c:
            r = await c.get("/environment/quota", headers={"X-Tenant-Key": TENANT})
        assert r.status_code == 200
        data = r.json()
        assert data["unlimited"] is False
        assert set(data["metrics"]) == {"daily_signals", "monthly_insights", "env_sources"}
        assert data["metrics"]["env_sources"]["limit"] == 3

    @pytest.mark.asyncio
    async def test_quota_default_tenant_unlimited(self, env_client):
        async with env_client as c:
            r = await c.get("/environment/quota")
        assert r.status_code == 200
        assert r.json()["unlimited"] is True

    @pytest.mark.asyncio
    async def test_feed_quota_block_and_truncation(self, env_client, monkeypatch):
        monkeypatch.setattr(um, "FREE_DAILY_SIGNALS", 2)
        for i in range(4):
            uns.publish_environment(
                source="env://policy/policy",
                payload={"title": f"政策{i}"},
                credibility="official",
            )
        async with env_client as c:
            r = await c.get("/environment/feed", headers={"X-Tenant-Key": TENANT})
        assert r.status_code == 200  # feed 永不 402
        data = r.json()
        assert len(data["signals"]) == 2
        assert data["quota"]["exhausted"] is True and data["quota"]["truncated"] == 2

    @pytest.mark.asyncio
    async def test_sessions_402_after_limit(self, sessions_client, monkeypatch):
        """sessions 走 get_tenant（fail-closed），须注册真实租户拿密钥。"""
        monkeypatch.setattr(um, "FREE_MONTHLY_INSIGHTS", 2)
        from src.runtime.tenant_store import tenant_store

        tid, api_key = await tenant_store.register("用量测试厂")
        try:
            headers = {"X-Tenant-Key": api_key}
            async with sessions_client as c:
                for _ in range(2):
                    r = await c.post("/sessions", json={"goal": "产量分析"}, headers=headers)
                    assert r.status_code == 200
                r = await c.post("/sessions", json={"goal": "产量分析"}, headers=headers)
            assert r.status_code == 402
            assert "信任爬梯③" in r.json()["detail"]
        finally:
            await tenant_store.delete(tid)

    @pytest.mark.asyncio
    async def test_sessions_default_tenant_not_metered(self, sessions_client, monkeypatch):
        monkeypatch.setattr(um, "FREE_MONTHLY_INSIGHTS", 1)
        async with sessions_client as c:
            for _ in range(3):
                r = await c.post("/sessions", json={"goal": "产量分析"})
                assert r.status_code == 200
