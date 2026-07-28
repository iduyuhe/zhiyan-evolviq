"""S3-7 体外感知大屏视图专项测试（#321）

覆盖：
1. /twin/external-perception 端点结构（全息视图字段齐全）
2. 空信号优雅降级（signal_count=0 / 分布为空 / 最近信号为空）
3. 类目分布（六维感知覆盖）聚合正确
4. 可信度分级分布（F4 治理）聚合正确
5. 三官方源健康呈现（policy/market/benchmark 含 mode 字段）

🔴 与孪生大屏其余区块同构：租户不可知的全息视图；require_auth 经 override 通过。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import FastAPI, Depends
from httpx import AsyncClient, ASGITransport

from src.runtime.uns import uns, CHANNEL_ENVIRONMENT, CRED_OFFICIAL, CRED_AUTHORITATIVE
from src.runtime.authn.deps import require_auth
from src.runtime.context import set_current_tenant
from src.runtime.api import twin


@pytest.fixture(autouse=True)
def clear_uns():
    uns._events.clear()
    yield
    uns._events.clear()


@pytest.fixture
def app():
    application = FastAPI()
    # 与主程序一致：twin 路由挂载 require_auth 依赖
    application.include_router(twin.router, dependencies=[Depends(require_auth)])
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


class TestExternalPerceptionStructure:
    @pytest.mark.asyncio
    async def test_endpoint_basic_structure(self, app):
        async with await _client(app) as c:
            r = await c.get("/twin/external-perception")
            assert r.status_code == 200, r.text
            d = r.json()
            for k in (
                "signal_count",
                "category_distribution",
                "credibility_distribution",
                "category_labels",
                "credibility_labels",
                "sources",
                "review",
                "recent_signals",
            ):
                assert k in d, f"缺失字段 {k}"
            # 三官方源健康
            names = {s["name"] for s in d["sources"]}
            assert {"policy", "market", "benchmark"}.issubset(names)
            # 审核队列结构
            assert set(d["review"].keys()) == {"pending", "approved", "rejected", "total"}
            # 标签映射存在（大屏友好名）
            assert d["category_labels"].get("policy") == "政策法规"
            assert d["credibility_labels"].get("official") == "官方"

    @pytest.mark.asyncio
    async def test_empty_signals_graceful(self, app):
        async with await _client(app) as c:
            r = await c.get("/twin/external-perception")
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["signal_count"] == 0
            assert d["category_distribution"] == {}
            assert d["credibility_distribution"] == {}
            assert d["recent_signals"] == []


class TestExternalPerceptionAggregation:
    @pytest.mark.asyncio
    async def test_category_distribution(self, app):
        uns.publish_environment(
            "policy", {"title": "P1", "category": "policy"},
            credibility=CRED_OFFICIAL,
        )
        uns.publish_environment(
            "policy", {"title": "P2", "category": "policy"},
            credibility=CRED_OFFICIAL,
        )
        uns.publish_environment(
            "market", {"title": "M1", "category": "market"},
            credibility=CRED_OFFICIAL,
        )
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            assert d["signal_count"] == 3
            assert d["category_distribution"].get("policy") == 2
            assert d["category_distribution"].get("market") == 1

    @pytest.mark.asyncio
    async def test_credibility_distribution(self, app):
        uns.publish_environment(
            "policy", {"title": "P1", "category": "policy"},
            credibility=CRED_OFFICIAL,
        )
        uns.publish_environment(
            "market", {"title": "M1", "category": "market"},
            credibility=CRED_AUTHORITATIVE,
        )
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            assert d["credibility_distribution"].get("official") == 1
            assert d["credibility_distribution"].get("authoritative") == 1

    @pytest.mark.asyncio
    async def test_source_health_has_mode(self, app):
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            for s in d["sources"]:
                assert "mode" in s
                assert "enabled" in s
                assert "label" in s

    @pytest.mark.asyncio
    async def test_recent_signals_sorted_and_trimmed(self, app):
        for i in range(15):
            uns.publish_environment(
                "policy", {"title": f"P{i}", "category": "policy"},
                credibility=CRED_OFFICIAL,
            )
        async with await _client(app) as c:
            d = (await c.get("/twin/external-perception")).json()
            # 最近信号最多 12 条
            assert len(d["recent_signals"]) <= 12
            assert len(d["recent_signals"]) == 12
            # 倒序：第一条应为最新（P14）
            assert d["recent_signals"][0]["title"] == "P14"
            # 字段裁剪：含 credibility / category / title
            first = d["recent_signals"][0]
            assert first["credibility"] == "official"
            assert first["category"] == "policy"
