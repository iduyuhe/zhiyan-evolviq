"""上铁通信实证（§3.7）内部隔离专项测试（杜总铁律：只做内部研究与实测，不对外宣传、非外界可见公开服务）

覆盖硬性隔离是否生效：
1. DisclosureSource 标记 internal_only=True
2. DisclosureSource 发布走独立内部通道 CHANNEL_ENVIRONMENT_INTERNAL，绝不进 CHANNEL_ENVIRONMENT 共享池
3. 孪生大屏体外感知视图 sources 不含 disclosure；recent_signals 不含 disclosure 标题
4. /environment/signals（客户面）不含 disclosure 信号
5. _known_source_names（租户订阅视图）不含 disclosure
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


class TestDisclosureSourceInternalOnly:
    def test_internal_only_flag(self):
        # 1. 源标记 internal_only=True
        assert DisclosureSource.internal_only is True
        src = DisclosureSource()
        assert src.internal_only is True
        # status() 透出该字段
        assert src.status().get("internal_only") is True

    def test_publishes_to_internal_channel_only(self):
        # 2. 发布走内部通道，不进共享池
        src = DisclosureSource()
        sid = src.publish_signal({
            "title": "中标某城市轨道交通通信系统集成项目（演示）",
            "content": "演示内容",
            "category": "disclosure",
            "entities": ["DISC:轨道交通装备"],
        })
        assert sid is not None
        internal = uns.query(channel=CHANNEL_ENVIRONMENT_INTERNAL, n=100)
        shared = uns.query(channel=CHANNEL_ENVIRONMENT, n=100)
        assert len(internal) == 1, "disclosure 必须进内部通道"
        assert internal[0]["payload"]["title"].startswith("中标")
        assert len(shared) == 0, "disclosure 绝不进 CHANNEL_ENVIRONMENT 共享池"
        # ALL_CHANNELS 含内部通道
        assert CHANNEL_ENVIRONMENT_INTERNAL in ALL_CHANNELS


class TestCustomerFacingExcludesDisclosure:
    @pytest.mark.asyncio
    async def test_twin_sources_exclude_disclosure(self, app):
        # 3a. 孪生大屏 sources 不含 disclosure
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            names = {s["name"] for s in d["sources"]}
            assert "disclosure" not in names, "孪生大屏不得暴露上铁实证源"
            assert {"policy", "market", "benchmark"}.issubset(names)

    @pytest.mark.asyncio
    async def test_twin_signals_exclude_disclosure(self, app):
        # 3b. 孪生大屏 recent_signals 不含 disclosure 标题
        DisclosureSource().publish_signal({
            "title": "上铁实证内部信号（不得外泄）",
            "content": "x", "category": "disclosure", "entities": [],
        })
        uns.publish_environment("policy", {"title": "政策P1", "category": "policy"}, credibility=CRED_OFFICIAL)
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            titles = {s["title"] for s in d["recent_signals"]}
            assert "上铁实证内部信号（不得外泄）" not in titles
            assert len(d["recent_signals"]) >= 1  # 政策信号可见

    @pytest.mark.asyncio
    async def test_environment_signals_exclude_disclosure(self, app):
        # 4. /environment/signals 不含 disclosure 信号
        DisclosureSource().publish_signal({
            "title": "上铁实证内部信号（不得外泄）",
            "content": "x", "category": "disclosure", "entities": [],
        })
        uns.publish_environment("market", {"title": "行情M1", "category": "market"}, credibility=CRED_OFFICIAL)
        async with await _client(app) as c:
            d = (await c.get("/environment/signals")).json()
            titles = {s["payload"].get("title") for s in d["signals"]}
            assert "上铁实证内部信号（不得外泄）" not in titles
            assert "行情M1" in titles

    @pytest.mark.asyncio
    async def test_environment_sources_exclude_disclosure(self, app):
        # 客户面 /environment/sources 不含 disclosure
        async with await _client(app) as c:
            d = (await c.get("/environment/sources")).json()
            names = {s["name"] for s in d["sources"]}
            assert "disclosure" not in names

    def test_known_source_names_excludes_disclosure(self):
        # 5. 租户订阅视图不含 disclosure
        from src.runtime.api.env_perception import _known_source_names
        assert "disclosure" not in _known_source_names()
