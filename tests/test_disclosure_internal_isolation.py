"""研究案例模式（§3.7）专项测试（杜总定调：对外匿名"某某通讯公司"，内部锚定真实上市公司）

覆盖研究案例模式是否正确落地：
1. DisclosureSource 标记 internal_only=False（对外匿名呈现，非内部-only）
2. DisclosureSource 发布走共享通道 CHANNEL_ENVIRONMENT（对外可见），绝不进内部通道 CHANNEL_ENVIRONMENT_INTERNAL
3. 🔴 匿名铁律：发布 payload 绝不携带真实公司名（real_anchor/company 字段被剥离）
4. 孪生大屏体外感知视图 sources 含 disclosure（匿名"某某通讯公司"）；recent_signals 含 disclosure 标题
5. /environment/signals（客户面）含 disclosure 信号
6. /environment/sources 含 disclosure
7. _known_source_names（租户订阅视图）不含 disclosure（tenant_facing=False，不占免费额度）
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI, Depends
from httpx import AsyncClient, ASGITransport

from src.runtime.uns import (
    uns,
    ALL_CHANNELS,
    CHANNEL_ENVIRONMENT,
    CHANNEL_ENVIRONMENT_INTERNAL,
    CRED_OFFICIAL,
)
from src.runtime.authn.deps import require_auth
from src.runtime.context import set_current_tenant
from src.runtime.env_sources.disclosure_source import DisclosureSource
from src.runtime.api import twin
from src.runtime.api import env_perception


@pytest.fixture(autouse=True)
def clear_uns():
    uns._events.clear()
    yield
    uns._events.clear()


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(twin.router, dependencies=[Depends(require_auth)])
    application.include_router(env_perception.router, dependencies=[Depends(require_auth)])
    return application


async def _client(app):
    app.dependency_overrides[require_auth] = lambda: {
        "tenant_id": "tA",
        "role": "TENANT_ADMIN",
        "username": "alice",
    }
    set_current_tenant("tA")
    t = ASGITransport(app=app)
    return AsyncClient(transport=t, base_url="http://t")


class TestDisclosureSourceAnonymizedExternal:
    def test_not_internal_only(self):
        # 1. 研究案例模式：对外匿名呈现（非 internal_only）
        assert DisclosureSource.internal_only is False
        src = DisclosureSource()
        assert src.internal_only is False
        assert src.status().get("internal_only") is False
        # 对外标签为匿名"某某通讯公司"
        assert "某某" in src.label
        # 内部锚定变量已填真实公司（杜总 2026-07-29 确认=中兴通讯）——且仅内部持有，绝不进 status()（防外泄）
        assert hasattr(src, "real_anchor")
        assert src.real_anchor == "中兴通讯（000063.SZ）"
        assert "real_anchor" not in src.status(), "真实锚定公司名不得经 status() 外泄"

    def test_publishes_to_shared_channel_only(self):
        # 2. 发布走共享通道，绝不进内部通道
        src = DisclosureSource()
        sid = src.publish_signal({
            "title": "中标某城市轨道交通通信系统集成项目（演示）",
            "content": "演示内容",
            "category": "disclosure",
            "entities": ["DISC:轨道交通装备"],
        })
        assert sid is not None
        shared = uns.query(channel=CHANNEL_ENVIRONMENT, n=100)
        internal = uns.query(channel=CHANNEL_ENVIRONMENT_INTERNAL, n=100)
        assert len(shared) == 1, "disclosure 必须进 CHANNEL_ENVIRONMENT 共享池（对外匿名可见）"
        assert shared[0]["payload"]["title"].startswith("中标")
        assert len(internal) == 0, "disclosure 绝不进内部通道"
        # 内部通道常量仍保留（供可选内部研究校验）
        assert CHANNEL_ENVIRONMENT_INTERNAL in ALL_CHANNELS

    def test_real_anchor_stripped_from_payload(self):
        # 3. 🔴 匿名铁律：真实公司名绝不进外发 payload
        src = DisclosureSource()
        src.real_anchor = "上海铁路通信有限公司"  # 模拟内部锚定真实公司
        sid = src.publish_signal({
            "title": "某上市公司公告（演示）",
            "content": "x",
            "category": "disclosure",
            "entities": [],
            "real_anchor": "上海铁路通信有限公司",  # 即使误带，也必须被剥离
            "company": "上海铁路通信有限公司",
        })
        assert sid is not None
        shared = uns.query(channel=CHANNEL_ENVIRONMENT, n=100)
        payload = shared[0]["payload"]
        assert "real_anchor" not in payload, "真实锚定公司名不得外泄"
        assert "company" not in payload, "真实公司名不得外泄"
        assert "上海铁路通信" not in str(payload), "payload 不得含真实公司名"
        # 源对象内部仍持有 real_anchor（内部研究用，不对外）
        assert src.real_anchor == "上海铁路通信有限公司"


class TestCustomerFacingShowsAnonymizedDisclosure:
    @pytest.mark.asyncio
    async def test_twin_sources_include_disclosure(self, app):
        # 4a. 孪生大屏 sources 含 disclosure（匿名"某某通讯公司"）
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            names = {s["name"] for s in d["sources"]}
            assert "disclosure" in names, "孪生大屏应匿名呈现研究案例源"
            assert {"policy", "market", "benchmark"}.issubset(names)
            disc = next(s for s in d["sources"] if s["name"] == "disclosure")
            assert "某某" in disc["label"]

    @pytest.mark.asyncio
    async def test_twin_signals_include_disclosure(self, app):
        # 4b. 孪生大屏 recent_signals 含 disclosure 标题
        DisclosureSource().publish_signal({
            "title": "某某通讯公司公告（对外匿名）",
            "content": "x", "category": "disclosure", "entities": [],
        })
        uns.publish_environment("policy", {"title": "政策P1", "category": "policy"}, credibility=CRED_OFFICIAL)
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            titles = {s["title"] for s in d["recent_signals"]}
            assert "某某通讯公司公告（对外匿名）" in titles
            assert len(d["recent_signals"]) >= 1

    @pytest.mark.asyncio
    async def test_environment_signals_include_disclosure(self, app):
        # 5. /environment/signals 含 disclosure 信号
        DisclosureSource().publish_signal({
            "title": "某某通讯公司公告（对外匿名）",
            "content": "x", "category": "disclosure", "entities": [],
        })
        uns.publish_environment("market", {"title": "行情M1", "category": "market"}, credibility=CRED_OFFICIAL)
        async with await _client(app) as c:
            d = (await c.get("/environment/signals")).json()
            titles = {s["payload"].get("title") for s in d["signals"]}
            assert "某某通讯公司公告（对外匿名）" in titles
            assert "行情M1" in titles

    @pytest.mark.asyncio
    async def test_environment_sources_include_disclosure(self, app):
        # 6. 客户面 /environment/sources 含 disclosure
        async with await _client(app) as c:
            d = (await c.get("/environment/sources")).json()
            names = {s["name"] for s in d["sources"]}
            assert "disclosure" in names

    def test_known_source_names_excludes_disclosure(self):
        # 7. 租户订阅视图不含 disclosure（tenant_facing=False，不占免费额度）
        from src.runtime.api.env_perception import _known_source_names
        assert "disclosure" not in _known_source_names()
