"""S2 v30.5 β 专项测试——租户环境订阅规则（#307 S2-1a）

覆盖：
1. 订阅存储：默认模板视图 / upsert / delete 回落 / credibility 校验
2. 免费额度：启用源数超上限 → QuotaExceeded / API 402（付费线③文案）
3. 语义隔离筛选 filter_signals：源开关 / credibility 阈值 / 关键词 include+exclude /
   未知源保守放行 official
4. API：订阅 CRUD + 先测试后保存闸门 + 未知源 404 + 租户隔离（A 改 B 不可见）
5. /environment/feed 租户过滤流
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.runtime import env_subscription_store as sub_mod
from src.runtime.api.env_perception import router
from src.runtime.env_subscription_store import (
    EnvSubscriptionStore,
    QuotaExceeded,
    env_subscription_store,
)
from src.runtime.uns import uns

KNOWN = ["policy", "market", "benchmark"]


# ============ Fixtures ============


@pytest.fixture(autouse=True)
def clean_store():
    """每个测试前后清空进程级订阅单例 + UNS 事件。"""
    env_subscription_store._by_tenant.clear()
    uns._events.clear()
    yield
    env_subscription_store._by_tenant.clear()
    uns._events.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _env_signal(name: str, credibility: str, title: str, entities=None):
    """构造一条平台级环境信号（dict 形，与 uns.query 输出同构）。"""
    return {
        "source": f"env://{name}/{name}",
        "channel": "environment",
        "credibility": credibility,
        "payload": {"title": title},
        "entities": entities or [],
    }


# ============ 1. 存储层 ============


class TestSubscriptionStore:
    def test_default_template_view(self):
        s = EnvSubscriptionStore()
        rules = s.list_for("t1", KNOWN)
        assert len(rules) == 3
        assert all(r["enabled"] and r.get("is_default") for r in rules)
        assert {r["source_name"] for r in rules} == set(KNOWN)

    @pytest.mark.asyncio
    async def test_upsert_and_get(self):
        s = EnvSubscriptionStore()
        d = await s.upsert("t1", "policy", credibility_min="official",
                           keywords_include=["钢铁"], known_sources=KNOWN)
        assert d["credibility_min"] == "official"
        assert d["keywords_include"] == ["钢铁"]
        rules = s.list_for("t1", KNOWN)
        explicit = [r for r in rules if not r.get("is_default")]
        assert len(explicit) == 1 and explicit[0]["source_name"] == "policy"

    @pytest.mark.asyncio
    async def test_delete_falls_back_to_default(self):
        s = EnvSubscriptionStore()
        await s.upsert("t1", "market", enabled=False, known_sources=KNOWN)
        assert s.enabled_count("t1", KNOWN) == 2
        assert await s.delete("t1", "market") is True
        # 回落默认模板 → 三源全启用
        assert s.enabled_count("t1", KNOWN) == 3
        assert await s.delete("t1", "market") is False  # 已无显式规则

    @pytest.mark.asyncio
    async def test_invalid_credibility_rejected(self):
        s = EnvSubscriptionStore()
        with pytest.raises(ValueError):
            await s.upsert("t1", "policy", credibility_min="rumor", known_sources=KNOWN)

    @pytest.mark.asyncio
    async def test_quota_exceeded(self, monkeypatch):
        monkeypatch.setattr(sub_mod, "FREE_MAX_SOURCES", 1)
        s = EnvSubscriptionStore()
        # 默认模板三源全启（超 1）→ 先关掉两个
        await s.upsert("t1", "market", enabled=False, known_sources=KNOWN)
        await s.upsert("t1", "benchmark", enabled=False, known_sources=KNOWN)
        await s.upsert("t1", "policy", enabled=True, known_sources=KNOWN)  # 1 个 OK
        with pytest.raises(QuotaExceeded):
            await s.upsert("t1", "market", enabled=True, known_sources=KNOWN)

    def test_tenant_isolation_in_store(self):
        s = EnvSubscriptionStore()
        s._by_tenant["tA"] = {}
        assert s.list_for("tB", KNOWN) != []  # B 只有默认模板
        assert all(r.get("is_default") for r in s.list_for("tB", KNOWN))


# ============ 2. 语义隔离筛选 ============


class TestFilterSignals:
    @pytest.mark.asyncio
    async def test_disabled_source_filtered(self):
        s = EnvSubscriptionStore()
        await s.upsert("t1", "market", enabled=False, known_sources=KNOWN)
        pool = [_env_signal("policy", "official", "P1"), _env_signal("market", "official", "M1")]
        out = s.filter_signals("t1", pool, KNOWN)
        assert [e["payload"]["title"] for e in out] == ["P1"]

    @pytest.mark.asyncio
    async def test_credibility_threshold(self):
        s = EnvSubscriptionStore()
        await s.upsert("t1", "policy", credibility_min="authoritative", known_sources=KNOWN)
        pool = [
            _env_signal("policy", "official", "OF"),
            _env_signal("policy", "authoritative", "AU"),
            _env_signal("policy", "general", "GE"),
        ]
        out = s.filter_signals("t1", pool, KNOWN)
        assert [e["payload"]["title"] for e in out] == ["OF", "AU"]

    @pytest.mark.asyncio
    async def test_keywords_include_exclude(self):
        s = EnvSubscriptionStore()
        await s.upsert("t1", "policy", keywords_include=["钢铁"],
                       keywords_exclude=["招聘"], known_sources=KNOWN)
        pool = [
            _env_signal("policy", "official", "钢铁行业新政"),
            _env_signal("policy", "official", "钢铁企业招聘规范"),
            _env_signal("policy", "official", "纺织行业新政"),
        ]
        out = s.filter_signals("t1", pool, KNOWN)
        assert [e["payload"]["title"] for e in out] == ["钢铁行业新政"]

    def test_unknown_source_only_official_passes(self):
        s = EnvSubscriptionStore()
        pool = [
            _env_signal("mystery", "official", "OF"),
            _env_signal("mystery", "general", "GE"),
        ]
        out = s.filter_signals("t1", pool, KNOWN)
        assert [e["payload"]["title"] for e in out] == ["OF"]

    def test_default_template_passes_all(self):
        """无任何显式规则：行业默认模板全收（general 起）。"""
        s = EnvSubscriptionStore()
        pool = [_env_signal("policy", "general", "GE"), _env_signal("market", "official", "OF")]
        assert len(s.filter_signals("t1", pool, KNOWN)) == 2


# ============ 3. API 层 ============


H_A = {"X-Tenant-Key": "TENANT_A"}
H_B = {"X-Tenant-Key": "TENANT_B"}


class TestSubscriptionAPI:
    @pytest.mark.asyncio
    async def test_list_default_view(self, client):
        async with client as c:
            r = await c.get("/environment/subscriptions", headers=H_A)
        assert r.status_code == 200
        body = r.json()
        assert body["tenant_id"] == "TENANT_A"
        assert len(body["subscriptions"]) == 3
        assert body["enabled_count"] == 3
        assert body["free_max_sources"] >= 1

    @pytest.mark.asyncio
    async def test_put_unknown_source_404(self, client):
        async with client as c:
            r = await c.put("/environment/subscriptions/nonexistent",
                            headers=H_A, json={"enabled": True})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_put_saves_with_test_gate(self, client):
        async with client as c:
            r = await c.put(
                "/environment/subscriptions/policy",
                headers=H_A,
                json={"enabled": True, "credibility_min": "official",
                      "keywords_include": ["制造"], "poll_interval_sec": 600},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "saved"
        assert body["subscription"]["credibility_min"] == "official"
        # 先测试后保存闸门：测试结果随响应返回（simulated 态 ok=True）
        assert body["test"] is not None and body["test"]["ok"] is True

    @pytest.mark.asyncio
    async def test_put_invalid_credibility_422(self, client):
        async with client as c:
            r = await c.put("/environment/subscriptions/policy",
                            headers=H_A, json={"credibility_min": "rumor"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_quota_402_with_upgrade_hint(self, client, monkeypatch):
        monkeypatch.setattr(sub_mod, "FREE_MAX_SOURCES", 1)
        async with client as c:
            await c.put("/environment/subscriptions/market",
                        headers=H_A, json={"enabled": False})
            await c.put("/environment/subscriptions/benchmark",
                        headers=H_A, json={"enabled": False})
            r = await c.put("/environment/subscriptions/market",
                            headers=H_A, json={"enabled": True})
        assert r.status_code == 402
        # 付费线③文案：引导接入内部数据源（信任爬梯）
        assert "信任爬梯" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_tenant_isolation_api(self, client):
        """A 关掉 market；B 视图不受影响（语义隔离红线）。"""
        async with client as c:
            r1 = await c.put("/environment/subscriptions/market",
                             headers=H_A, json={"enabled": False})
            assert r1.status_code == 200
            ra = await c.get("/environment/subscriptions", headers=H_A)
            rb = await c.get("/environment/subscriptions", headers=H_B)
        a_market = next(s for s in ra.json()["subscriptions"] if s["source_name"] == "market")
        b_market = next(s for s in rb.json()["subscriptions"] if s["source_name"] == "market")
        assert a_market["enabled"] is False and not a_market.get("is_default")
        assert b_market["enabled"] is True and b_market.get("is_default")

    @pytest.mark.asyncio
    async def test_delete_and_fallback(self, client):
        async with client as c:
            await c.put("/environment/subscriptions/policy",
                        headers=H_A, json={"enabled": False})
            r1 = await c.delete("/environment/subscriptions/policy", headers=H_A)
            r2 = await c.delete("/environment/subscriptions/policy", headers=H_A)
        assert r1.status_code == 200 and r1.json()["fallback"] == "default_template"
        assert r2.status_code == 404  # 已无显式规则

    @pytest.mark.asyncio
    async def test_feed_respects_rules(self, client):
        """/feed：A 只订 policy×official；B 默认模板全收。"""
        uns.publish_environment(source="env://policy/policy", payload={"title": "官方新政"},
                                entities=[], credibility="official")
        uns.publish_environment(source="env://market/market", payload={"title": "行情波动"},
                                entities=[], credibility="general")
        async with client as c:
            await c.put("/environment/subscriptions/market",
                        headers=H_A, json={"enabled": False})
            ra = await c.get("/environment/feed", headers=H_A)
            rb = await c.get("/environment/feed", headers=H_B)
        titles_a = [s["payload"]["title"] for s in ra.json()["signals"]]
        titles_b = [s["payload"]["title"] for s in rb.json()["signals"]]
        assert "行情波动" not in titles_a and "官方新政" in titles_a
        assert set(titles_b) >= {"官方新政", "行情波动"}
        assert ra.json()["visible"] < ra.json()["pool_size"] or ra.json()["pool_size"] == 1
