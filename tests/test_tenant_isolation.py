"""多租户隔离 + 鉴权边界对抗测试（P0/P1 修复验证）。

专门验证：
- P0：匿名上下文为 viewer（最小权限），不再是 SUPERADMIN；不能访问管理端点。
- P1：写回提交的 tenant 由鉴权上下文决定，忽略请求体 tenant_id（防越权写他租户）。
- P1：/writeback/pending、/stats 仅返回当前租户数据（防跨租户读）。
- P0+P1：非 SUPERADMIN 的 KG query tenant 参数被忽略（既证明角色非超管，又防越权读他租户）。
"""
import httpx
import pytest

from src.runtime.main import app


def _client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://t")


@pytest.mark.asyncio
async def test_anonymous_cannot_admin_p0():
    """P0：匿名（viewer）访问 require_role(tenant_admin) 建用户端点必须被拒（401/403）。"""
    async with _client() as t:
        r = await t.post(
            "/authn/users",
            json={"username": "evil", "password": "x", "role": "operator", "tenant_id": "default"},
        )
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_writeback_ignores_client_tenant_p1():
    """P1：提交时请求体 tenant_id 被忽略，记录归属当前鉴权租户。"""
    async with _client() as t:
        r = await t.post(
            "/writeback",
            json={
                "system": "mes",
                "agent": "supply_chain",
                "decision_type": "z",
                "payload": {"v": 1},
                "tenant_id": "EVIL_TENANT",  # 应被忽略
            },
            headers={"X-Tenant-Key": "TENANT_A"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "pending"
        s = await t.get("/writeback/stats", headers={"X-Tenant-Key": "TENANT_A"})
        assert s.json()["tenant_id"] == "TENANT_A"
        # EVIL_TENANT 不应有任何记录（越权写被阻断）
        e = await t.get("/writeback/stats", headers={"X-Tenant-Key": "EVIL_TENANT"})
        assert e.json()["pending"] == 0


@pytest.mark.asyncio
async def test_writeback_pending_isolation_p1():
    """P1：TENANT_A 的 pending 不被 OTHER 租户看见（跨租户读被阻断）。"""
    async with _client() as t:
        await t.post(
            "/writeback",
            json={"system": "erp", "agent": "x", "decision_type": "t", "payload": {"v": 2}},
            headers={"X-Tenant-Key": "TENANT_A"},
        )
        p = await t.get("/writeback/pending", headers={"X-Tenant-Key": "OTHER_TENANT"})
        assert len(p.json()["pending"]) == 0
        mine = await t.get("/writeback/pending", headers={"X-Tenant-Key": "TENANT_A"})
        assert len(mine.json()["pending"]) >= 1


@pytest.mark.asyncio
async def test_kg_query_ignores_spoofed_tenant_p0_p1():
    """P0+P1：匿名（viewer）的 KG query tenant 参数被忽略，不能越权读他租户。

    若匿名仍是 SUPERADMIN，tenant=SPOOFED_TENANT 会被原样采纳；改为 viewer 后忽略。
    """
    async with _client() as t:
        r = await t.get("/kg/query?label=Material&tenant=SPOOFED_TENANT")
        assert r.status_code == 200
        assert r.json().get("tenant") != "SPOOFED_TENANT"
