"""S2-3 无感转型三圈解锁进度测试（#310）

覆盖：
1. 三圈映射完整性——25 agent 全集、无重复、与 AGENT_REGISTRY 对齐
2. 圈层判定：外圈（默认）→ 中圈（gateway_config 非空=信任爬梯③）→ 内圈（私有化 env）
3. API：/environment/unlock-progress 形状 + quota 摘要内嵌 + 租户区分
4. F4 纪律：next_step 为事实说明（每圈都有文案，不为空）
"""

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport

from src.runtime.main import app
from src.runtime import unlock_map
from src.runtime.unlock_map import (
    CIRCLES, INNER_AGENTS, MIDDLE_AGENTS, NEXT_STEP, OUTER_AGENTS,
    current_circle, progress_view,
)

TENANT_A = "t-unlock-a"


def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------- 1. 三圈映射完整性 ----------

class TestCircleMap:
    def test_25_agents_no_overlap(self):
        all_ids = OUTER_AGENTS + MIDDLE_AGENTS + INNER_AGENTS
        assert len(all_ids) == 25
        assert len(set(all_ids)) == 25, "三圈成员不得重复"

    def test_alignment_with_agent_registry(self):
        from src.runtime.api.agents_api import AGENT_REGISTRY

        registry_ids = {a["id"] for a in AGENT_REGISTRY}
        circle_ids = set(OUTER_AGENTS + MIDDLE_AGENTS + INNER_AGENTS)
        assert circle_ids == registry_ids, (
            f"三圈映射与 AGENT_REGISTRY 不一致：缺 {registry_ids - circle_ids}，"
            f"多 {circle_ids - registry_ids}"
        )

    def test_outer_is_g_mode_free_five(self):
        # 总纲 §3.5：外圈纯环境信号可用（G 模式严格不变）
        # 2026-08-02：bid_intel（商机情报）加入外圈——纯消费 customer_voice+benchmark+market，
        # 不依赖租户内部数据，仍符合「外圈纯环境信号」定义（4→5）
        assert set(OUTER_AGENTS) == {
            "executive_cockpit", "supply_chain", "procurement_manage", "compliance_q", "bid_intel",
        }

    def test_every_circle_has_next_step(self):
        for c in CIRCLES:
            assert NEXT_STEP.get(c["key"]), f"圈层 {c['key']} 缺 next_step 文案"


# ---------- 2. 圈层判定 ----------

class TestCurrentCircle:
    def test_default_is_outer(self, monkeypatch):
        monkeypatch.delenv("ZHIYAN_PRIVATE_DEPLOYMENT", raising=False)
        assert current_circle("t-nobody") == "outer"

    @pytest.mark.asyncio
    async def test_gateway_config_unlocks_middle(self, monkeypatch):
        monkeypatch.delenv("ZHIYAN_PRIVATE_DEPLOYMENT", raising=False)
        from src.runtime.tenant_store import tenant_store

        tid, _key = await tenant_store.register("解锁测试厂A")
        try:
            assert current_circle(tid) == "outer"
            await tenant_store.set_gateway_config(tid, {"protocol": "opcua"})
            assert current_circle(tid) == "middle"
        finally:
            await tenant_store.delete(tid)

    def test_private_deployment_unlocks_inner(self, monkeypatch):
        monkeypatch.setenv("ZHIYAN_PRIVATE_DEPLOYMENT", "1")
        assert current_circle("t-anyone") == "inner"


# ---------- 3. progress_view 形状 ----------

class TestProgressView:
    def test_outer_view(self, monkeypatch):
        monkeypatch.delenv("ZHIYAN_PRIVATE_DEPLOYMENT", raising=False)
        v = progress_view("t-nobody")
        assert v["current_circle"] == "outer"
        assert v["unlocked_agents"] == 5
        assert v["total_agents"] == 25
        by_key = {c["key"]: c for c in v["circles"]}
        assert by_key["outer"]["unlocked"] is True
        assert by_key["middle"]["unlocked"] is False
        assert by_key["inner"]["unlocked"] is False
        assert "内部数据源" in v["next_step"]

    def test_inner_view_all_unlocked(self, monkeypatch):
        monkeypatch.setenv("ZHIYAN_PRIVATE_DEPLOYMENT", "1")
        v = progress_view("t-anyone")
        assert v["unlocked_agents"] == 25
        assert all(c["unlocked"] for c in v["circles"])


# ---------- 4. API 端点 ----------

class TestUnlockAPI:
    @pytest.mark.asyncio
    async def test_endpoint_shape_and_quota_embedded(self, monkeypatch):
        monkeypatch.delenv("ZHIYAN_PRIVATE_DEPLOYMENT", raising=False)
        async with _client() as c:
            r = await c.get("/environment/unlock-progress",
                            headers={"X-Tenant-Key": TENANT_A})
            assert r.status_code == 200
            data = r.json()
        assert data["current_circle"] == "outer"
        assert len(data["circles"]) == 3
        # quota 摘要内嵌，前端一次请求渲染
        assert "metrics" in data["quota"]
        assert "daily_signals" in data["quota"]["metrics"]

    @pytest.mark.asyncio
    async def test_anonymous_never_500(self):
        # 匿名在测试环境降 viewer（P0 收口语义）→ 200 走 default 租户；
        # 生产 fail-closed 下为 401/403。任何情况不得 500。
        async with _client() as c:
            r = await c.get("/environment/unlock-progress")
        assert r.status_code in (200, 401, 403)
        if r.status_code == 200:
            assert r.json()["tenant_id"] == "default"

    @pytest.mark.asyncio
    async def test_middle_tenant_view(self, monkeypatch):
        monkeypatch.delenv("ZHIYAN_PRIVATE_DEPLOYMENT", raising=False)
        from src.runtime.tenant_store import tenant_store

        tid, _key = await tenant_store.register("解锁测试厂B")
        try:
            await tenant_store.set_gateway_config(tid, {"protocol": "modbus"})
            async with _client() as c:
                # conftest 开 dev-trust：X-Tenant-Key 原值即 tenant_id
                r = await c.get("/environment/unlock-progress",
                                headers={"X-Tenant-Key": tid})
                assert r.status_code == 200
                data = r.json()
            assert data["current_circle"] == "middle"
            # middle=8 + outer=5 = 13 已解锁（2026-07-29 中圈补齐 4 个范式治理类；2026-08-02 外圈+bid_intel）
            assert data["unlocked_agents"] == 13
            # 信任爬梯③ → 免限额（quota 与解锁语义同源）
            assert data["quota"]["unlimited"] is True
        finally:
            await tenant_store.delete(tid)
