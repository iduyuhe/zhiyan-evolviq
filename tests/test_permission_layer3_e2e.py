"""权限第③层「生产有牙」端到端执法测试（#431 / #433 / #434，2026-08-01）

前置事实（本轮实测确认，勿再重复排查）：
- `src/runtime/main.py` 已对全部业务路由挂 `dependencies=[Depends(require_auth)]`，
  `require_auth` 内部 `_bind_capability(user)` 把 capability 钉进 contextvar，
  因此后端 403 执法链**早已完备**（见 tests/test_permission_capability.py 18 项）。
- 真实缺口有三：①种子案例账号没设岗位（第③层在生产里"无牙"）；
  ②登录用户不带 X-Tenant-Key 时数据落 default 租户；
  ③`GET /authn/users` 不带 tenant_id 时 tenant_admin 能列出全平台用户（跨租户泄漏）。

本文件用**真实种子账号走真实登录**验证上述三项已收口：
- telecom_viewer = supply_manager → 成本/驾驶舱类目标 403
- telecom_admin  = plant_manager  → 全量放行 200
- semicon_viewer = device_engineer → 设备类放行、供应链类拒绝
- 登录租户用户不带 key → 数据落自身租户（不再回落 default）
- tenant_admin 列用户/改岗位 → 强制锁定自身租户

🔴 匿名铁律：所有对外 payload 断言零真名（中兴/中芯/ZTE/SMIC/证券代码）。
"""

import json

import httpx
import pytest
from httpx import ASGITransport

from src.runtime.seed_case_tenants import default_password

LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte", "中芯", "SMIC", "smic", "688981"]

# 目标语句 → 期望路由到的 agent（与 ROUTING_RULES 对齐）
GOAL_COST = "分析单位制造成本拆解与降本机会"
GOAL_SUPPLY = "检查关键物料库存与供应链断供风险"
GOAL_DEVICE = "检查设备健康状况与预测维护建议"


def _assert_no_leak(payload, where: str):
    blob = json.dumps(payload, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


async def _ensure_seeded():
    """幂等开通研究案例租户（含岗位补齐）。"""
    from src.runtime.seed_case_tenants import seed_case_tenants

    return await seed_case_tenants()


async def _login(client: httpx.AsyncClient, username: str) -> dict:
    r = await client.post(
        "/authn/login",
        json={"username": username, "password": default_password(username)},
    )
    assert r.status_code == 200, f"{username} 登录失败：{r.text}"
    body = r.json()
    assert body.get("access_token"), body
    return body


def _auth(token: str) -> dict:
    """只带 Bearer，**故意不带 X-Tenant-Key** —— 验证 JWT 租户优先解析。"""
    return {"Authorization": f"Bearer {token}"}


async def _client():
    return httpx.AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test")


def _app():
    from src.runtime.main import app

    return app


# ──────────────────── 1. #433 种子给案例账号设了真实岗位 ────────────────────


@pytest.mark.asyncio
async def test_case_tenant_accounts_carry_business_role():
    """研究案例账号建号即带岗位；已存在的老账号也会被幂等补齐。"""
    from src.runtime.authn.service import authn_service

    await _ensure_seeded()

    expected = {
        "telecom_admin": "plant_manager",
        "telecom_viewer": "supply_manager",
        "semicon_admin": "plant_manager",
        "semicon_viewer": "device_engineer",
    }
    for uname, biz in expected.items():
        rec = await authn_service._load(uname)
        assert rec, f"账号缺失：{uname}"
        assert rec.get("business_role") == biz, f"{uname} 岗位应为 {biz}，实际 {rec.get('business_role')}"
        if biz != "plant_manager":  # 厂长是全放行，作用域可为通配
            scope = rec.get("capability_scope") or {}
            allowed = scope.get("allowed_agents") or []
            assert allowed and "*" not in allowed, f"{uname} 作用域应受限，实际 {allowed}"


# ──────────────────── 2. #434 真实登录 → 越权 403 / 授权 200 ────────────────────


@pytest.mark.asyncio
async def test_viewer_denied_cost_analysis_via_real_login():
    """供应链经理（telecom_viewer）打成本分析 → 403 capability_denied。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_viewer"))["access_token"]
        r = await c.post("/sessions", json={"goal": GOAL_COST}, headers=_auth(tok))
        assert r.status_code == 403, r.text
        body = r.json()
        assert body.get("error") == "capability_denied"
        assert body.get("agent") == "cost_analysis"
        _assert_no_leak(body, "capability_denied 响应")


@pytest.mark.asyncio
async def test_viewer_allowed_in_scope_agent():
    """作用域内（供应链）应正常放行。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_viewer"))["access_token"]
        r = await c.post("/sessions", json={"goal": GOAL_SUPPLY}, headers=_auth(tok))
        assert r.status_code == 200, r.text
        _assert_no_leak(r.json(), "供应链会话响应")


@pytest.mark.asyncio
async def test_plant_manager_admin_unrestricted():
    """厂长（telecom_admin）成本分析应放行。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        r = await c.post("/sessions", json={"goal": GOAL_COST}, headers=_auth(tok))
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_semicon_device_engineer_scope():
    """设备工程师：设备类放行、供应链类拒绝（半导体行业模板）。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "semicon_viewer"))["access_token"]

        ok = await c.post("/sessions", json={"goal": GOAL_DEVICE}, headers=_auth(tok))
        assert ok.status_code == 200, ok.text

        denied = await c.post("/sessions", json={"goal": GOAL_SUPPLY}, headers=_auth(tok))
        assert denied.status_code == 403, denied.text
        assert denied.json().get("error") == "capability_denied"


# ──────────────────── 3. #432 /authn/my-agents 是前端菜单唯一真相源 ────────────────────


@pytest.mark.asyncio
async def test_my_agents_filtered_for_restricted_viewer():
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_viewer"))["access_token"]
        r = await c.get("/authn/my-agents", headers=_auth(tok))
        assert r.status_code == 200, r.text
        body = r.json()
        ids = {a["id"] for a in body["agents"]}

        assert body["business_role"] == "supply_manager"
        assert body["business_role_label"] and body["business_role_label"] != "未设置"
        assert body["unrestricted"] is False
        assert "supply_chain" in ids
        assert "cost_analysis" not in ids, "供应链经理不应看到成本分析"
        assert "executive_cockpit" not in ids, "供应链经理不应看到高管驾驶舱"
        assert body["total"] == len(ids)
        # 只读标记应透传（industry_research 为只读）
        ro = {a["id"] for a in body["agents"] if a.get("read_only")}
        assert "industry_research" in ro
        _assert_no_leak(body, "/authn/my-agents（viewer）")


@pytest.mark.asyncio
async def test_my_agents_unrestricted_for_plant_manager():
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        body = (await c.get("/authn/my-agents", headers=_auth(tok))).json()
        ids = {a["id"] for a in body["agents"]}
        assert body["unrestricted"] is True
        assert {"cost_analysis", "executive_cockpit", "supply_chain"} <= ids
        assert body["total"] >= 20, f"厂长应看到全量智能体，实际 {body['total']}"


# ──────────────────── 4. #431 登录租户用户不带 key 也不落 default ────────────────────


@pytest.mark.asyncio
async def test_tenant_resolved_from_jwt_without_tenant_key():
    """真实租户用户不带 X-Tenant-Key → 数据落自身租户，而不是 default。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        r = await c.post("/sessions", json={"goal": GOAL_COST}, headers=_auth(tok))
        assert r.status_code == 200, r.text
        assert r.json()["tenant_id"] == "telecom", r.json()


@pytest.mark.asyncio
async def test_jwt_tenant_beats_spoofed_tenant_key():
    """租户用户即便伪造 X-Tenant-Key 指向别家，也钉死在自身租户（防串台）。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "semicon_admin"))["access_token"]
        headers = {**_auth(tok), "X-Tenant-Key": "telecom"}
        r = await c.post("/sessions", json={"goal": GOAL_DEVICE}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["tenant_id"] == "semicon", "伪造 key 不得改变归属租户"


@pytest.mark.asyncio
async def test_superadmin_can_still_switch_tenant_by_key():
    """超级管理员保留跨租户运维能力（X-Tenant-Key 仍按真实密钥生效）。

    注意 `get_tenant` 对 X-Tenant-Key 恒为 fail-closed（不吃 DEV_TRUST），
    因此这里现场注册一个租户拿明文 key，而不是拿裸 tenant_id 冒充。
    """
    from src.runtime.authn.security import encode_jwt
    from src.runtime.tenant_store import tenant_store

    await _ensure_seeded()
    ops_tid, ops_key = await tenant_store.register("超管运维验证租户")
    assert ops_key, "首次注册应返回明文 key"

    token = encode_jwt({"sub": "root_ops", "role": "SUPERADMIN", "tenant_id": "default"})
    async with await _client() as c:
        r = await c.post(
            "/sessions",
            json={"goal": GOAL_DEVICE},
            headers={"Authorization": f"Bearer {token}", "X-Tenant-Key": ops_key},
        )
        assert r.status_code == 200, r.text
        assert r.json()["tenant_id"] == ops_tid


@pytest.mark.asyncio
async def test_enterprise_user_ignores_valid_foreign_tenant_key():
    """企业用户即便持有**有效**的别家租户 key，也仍钉死在自身租户。"""
    from src.runtime.tenant_store import tenant_store

    await _ensure_seeded()
    _, foreign_key = await tenant_store.register("外部租户（越权探测用）")
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        r = await c.post(
            "/sessions",
            json={"goal": GOAL_DEVICE},
            headers={**_auth(tok), "X-Tenant-Key": foreign_key},
        )
        assert r.status_code == 200, r.text
        assert r.json()["tenant_id"] == "telecom", "持有效外部 key 也不得跨租户"


# ──────────────────── 5. 跨租户越权收口（本轮新发现的缺口） ────────────────────


@pytest.mark.asyncio
async def test_tenant_admin_user_list_scoped_to_own_tenant():
    """tenant_admin 列用户只能看到自己租户（此前不带 tenant_id 可列全平台）。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        r = await c.get("/authn/users", headers=_auth(tok))
        assert r.status_code == 200, r.text
        body = r.json()
        users = body.get("users", body if isinstance(body, list) else [])
        assert users, body
        tids = {u.get("tenant_id") for u in users}
        assert tids == {"telecom"}, f"越权看到其它租户：{tids}"
        names = {u.get("username") for u in users}
        assert "semicon_admin" not in names
        _assert_no_leak(body, "/authn/users（telecom_admin）")


@pytest.mark.asyncio
async def test_tenant_admin_cannot_query_other_tenant_by_param():
    """显式传别家 tenant_id 也会被强制改写回自身租户。"""
    await _ensure_seeded()
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        r = await c.get("/authn/users", params={"tenant_id": "semicon"}, headers=_auth(tok))
        assert r.status_code == 200, r.text
        body = r.json()
        users = body.get("users", body if isinstance(body, list) else [])
        tids = {u.get("tenant_id") for u in users}
        assert tids <= {"telecom"}, f"tenant_id 参数越权生效：{tids}"


@pytest.mark.asyncio
async def test_tenant_admin_cannot_change_other_tenant_capability():
    """跨租户改岗位 → 404（不暴露对方存在性）。"""
    from src.runtime.authn.service import authn_service

    await _ensure_seeded()
    victim = await authn_service._load("semicon_viewer")
    assert victim
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        r = await c.post(
            f"/authn/users/{victim['id']}/capability",
            json={"business_role": "plant_manager"},
            headers=_auth(tok),
        )
        assert r.status_code == 404, r.text

    # 受害者岗位不得被改动
    after = await authn_service._load("semicon_viewer")
    assert after.get("business_role") == "device_engineer"


@pytest.mark.asyncio
async def test_tenant_admin_can_change_own_tenant_capability():
    """同租户内改岗位应成功，且立刻反映到可见清单（授权闭环）。"""
    from src.runtime.authn.service import authn_service
    from src.presets.permission_templates import scope_for_business_role

    await _ensure_seeded()
    target = await authn_service._load("telecom_viewer")
    assert target
    async with await _client() as c:
        tok = (await _login(c, "telecom_admin"))["access_token"]
        try:
            r = await c.post(
                f"/authn/users/{target['id']}/capability",
                json={"business_role": "finance_controller"},
                headers=_auth(tok),
            )
            assert r.status_code == 200, r.text

            vt = (await _login(c, "telecom_viewer"))["access_token"]
            ids = {a["id"] for a in (await c.get("/authn/my-agents", headers=_auth(vt))).json()["agents"]}
            assert "cost_analysis" in ids, "改岗为财务后应看得到成本分析"
            assert "supply_chain" not in ids, "财务不应保留供应链视野"
        finally:
            # 还原，避免污染其它用例与生产语义
            await authn_service.set_capability(
                target["id"],
                business_role="supply_manager",
                capability_scope=scope_for_business_role(
                    "supply_manager", industry="telecom_equipment"
                ),
            )
    restored = await authn_service._load("telecom_viewer")
    assert restored.get("business_role") == "supply_manager"
