"""S2-4 #314：G5 轨道二 platform_insight 专项测试

覆盖：
- UNS 新增 platform_insight 通道（与 environment 真实情报严格分离）
- 规则化派生：基于真实情报生成平台建议，透明溯源 based_on
- 去重幂等：同一真实信号 + 同一模板只生成一次
- /feed 合并：真实情报(kind=intelligence) 与平台建议(kind=platform_insight) 相邻呈现
- F4 红线：平台建议 credibility 永远是 platform，绝不伪装成 official 情报
- API 派生幂等：POST /environment/pull 多次不重复生成
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.platform_insight_store import platform_insight_store
from src.runtime.uns import CHANNEL_ENVIRONMENT, CHANNEL_PLATFORM_INSIGHT, CRED_PLATFORM, uns

pytestmark = pytest.mark.asyncio


# 隔离：platform_insight_store 是进程级单例，必须每个测试前后清空，
# 避免本文件生成的平台建议泄漏进其他测试文件的 /feed（如用量计量测试）。
@pytest.fixture(autouse=True)
def _isolate_store():
    platform_insight_store.clear()
    yield
    platform_insight_store.clear()


TEST_ADMIN_PW = "TestAdmin123!"


def _client():
    from src.runtime.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _admin_token() -> str:
    from src.runtime.authn.service import authn_service

    await authn_service.ensure_admin(password=TEST_ADMIN_PW)
    from src.runtime.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})
        return r.json()["access_token"]


def _publish_benchmark_aps():
    """发布一条命中 benchmark_aps 模板的真实对标情报。"""
    return uns.publish_environment(
        source="env://benchmark/demo",
        payload={
            "title": "电子行业灯塔工厂 AI 排产实践（测试）",
            "content": "标杆企业普遍实现排产决策分钟级响应，OEE 显著提升。",
        },
        credibility="official",
    )


def _publish_market_up():
    """发布一条命中 market_bom 模板的真实行情情报。"""
    return uns.publish_environment(
        source="env://market/demo",
        payload={
            "title": "电解铜现货均价周报（测试）",
            "content": "本周电解铜价格环比上行约 2%，建议关注锁价窗口。",
            "entities": ["MAT:电解铜"],
        },
        credibility="official",
    )


def _publish_policy_subsidy():
    """发布一条命中 subsidy 模板的真实政策情报。"""
    return uns.publish_environment(
        source="env://policy/demo",
        payload={
            "title": "中小企业智能化改造补贴申报启动（测试）",
            "content": "多地开放数字化转型改造补贴申领窗口。",
        },
        credibility="official",
    )


# ---------- UNS 通道分离 ----------

class TestUNSChannel:
    async def test_publish_platform_insight_channel_and_credibility(self):
        ev = uns.publish_platform_insight(
            source="platform://zhiyan/suggestion",
            payload={"title": "t", "content": "c"},
            tenant_id="default",
        )
        assert ev.channel == CHANNEL_PLATFORM_INSIGHT
        assert ev.credibility == CRED_PLATFORM
        # 与 environment 真实情报通道严格分离
        assert ev.channel != CHANNEL_ENVIRONMENT
        events = uns.query(channel=CHANNEL_PLATFORM_INSIGHT)
        assert any(e["id"] == ev.id for e in events)

    async def test_platform_insight_never_official(self):
        ev = uns.publish_platform_insight(source="platform://zhiyan/suggestion", payload={"title": "x"})
        assert ev.credibility == "platform"
        assert ev.credibility != "official"


# ---------- 规则化派生 + 去重 ----------

class TestDeriveAndDedup:
    def setup_method(self):
        platform_insight_store.clear()

    async def test_derive_from_real_intelligence(self):
        _publish_benchmark_aps()
        n = await platform_insight_store.generate_from_environment(tenant_id="default")
        assert n >= 1
        items = platform_insight_store.list_for(n=50)
        assert any(it["kind"] == "platform_insight" for it in items)
        it = next(it for it in items if it["kind"] == "platform_insight")
        assert it["credibility"] == "platform"
        # 透明溯源：based_on 指向真实情报
        assert isinstance(it["based_on"], list) and len(it["based_on"]) >= 1
        assert it["based_on"][0].get("signal_id")

    async def test_dedup_idempotent(self):
        _publish_benchmark_aps()
        n1 = await platform_insight_store.generate_from_environment(tenant_id="default")
        assert n1 >= 1
        first = platform_insight_store.count()
        # 再次基于相同真实情报派生 → 不新增
        n2 = await platform_insight_store.generate_from_environment(tenant_id="default")
        assert n2 == 0
        assert platform_insight_store.count() == first


# ---------- /feed 合并 + F4 红线 ----------

class TestFeedMerge:
    def setup_method(self):
        platform_insight_store.clear()

    async def test_feed_merges_intelligence_and_platform_insight(self):
        _publish_benchmark_aps()
        _publish_market_up()
        _publish_policy_subsidy()
        await platform_insight_store.generate_from_environment(tenant_id="default")

        token = await _admin_token()
        async with _client() as c:
            r = await c.get(
                "/environment/feed?n=30",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        signals = body["signals"]
        kinds = {s.get("kind") for s in signals}
        assert "intelligence" in kinds
        assert "platform_insight" in kinds
        assert body["platform_insight_count"] > 0

    async def test_f4_red_line_platform_never_official(self):
        _publish_benchmark_aps()
        await platform_insight_store.generate_from_environment(tenant_id="default")

        token = await _admin_token()
        async with _client() as c:
            r = await c.get(
                "/environment/feed?n=30",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        for s in r.json()["signals"]:
            if s.get("kind") == "platform_insight":
                # 红线：平台建议 credibility 永远是 platform，绝不伪装成官方情报
                assert s["credibility"] == "platform"
                assert s["credibility"] != "official"

    async def test_platform_insights_endpoint(self):
        _publish_benchmark_aps()
        await platform_insight_store.generate_from_environment(tenant_id="default")
        token = await _admin_token()
        async with _client() as c:
            r = await c.get(
                "/environment/platform-insights?n=50",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] > 0
        assert all(it["kind"] == "platform_insight" for it in body["insights"])
        assert all(it["credibility"] == "platform" for it in body["insights"])


# ---------- API 派生幂等（pull 触发） ----------

class TestAPIDedup:
    def setup_method(self):
        platform_insight_store.clear()

    async def test_pull_triggers_generation_idempotent(self):
        _publish_benchmark_aps()
        token = await _admin_token()
        async with _client() as c:
            h = {"Authorization": f"Bearer {token}"}
            r1 = await c.post("/environment/pull?limit=10", headers=h)
            assert r1.status_code == 200
            f1 = (await c.get("/environment/feed?n=30", headers=h)).json()
            # 第二次拉取（真实情报已在池中）→ 平台建议不应重复生成
            await c.post("/environment/pull?limit=10", headers=h)
            f2 = (await c.get("/environment/feed?n=30", headers=h)).json()
        assert f1["platform_insight_count"] > 0
        assert f2["platform_insight_count"] == f1["platform_insight_count"]
