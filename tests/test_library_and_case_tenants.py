"""#425 / #427 / #428 / #429 收口测试（2026-07-29）

覆盖四件事：
- #425 路由错位修复：「列出所有研究案例 / 案例列表 / case_xxx 详情」稳定命中 case_curator，
  「研究案例推演 / 行业研究」仍归 industry_research。
- #427 预设库 / 案例库只读 REST：/presets/library、/presets/library/{industry}、
  /cases/library、/cases/library/{id}、/cases/my。
- #428 企业入驻 Agent 接上设备预设（equipment_presets 字段）。
- #429 研究案例租户破例直连实例化（telecom / semicon 可登录，绑定案例）。

🔴 匿名铁律：所有对外 payload 断言零真名（中兴/中芯/000063/ZTE/SMIC）。
"""

import json

import pytest

from src.runtime.agent.router import route_goal

LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte", "中芯", "SMIC", "smic", "688981"]


def _assert_no_leak(payload, where: str):
    blob = json.dumps(payload, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


@pytest.fixture
async def async_client_admin():
    """带 JWT 的 ASGI 客户端（default 租户 tenant_admin）。"""
    from httpx import ASGITransport, AsyncClient

    from src.runtime.authn.security import encode_jwt
    from src.runtime.main import app

    token = encode_jwt({"sub": "lib_tester", "role": "TENANT_ADMIN", "tenant_id": "default"})
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c


# ───────────────────────── #425 路由错位 ─────────────────────────


@pytest.mark.parametrize("goal", [
    "列出所有研究案例",
    "全部研究案例",
    "研究案例列表",
    "研究案例清单",
    "列出研究案例",
    "案例列表",
    "案例清单",
    "列出案例",
    "全部案例",
    "所有案例",
    "案例库汇总",
    "case_telecom_2026 详情",
    "查看 case_semicon_2026",
])
def test_case_library_intents_route_to_case_curator(goal):
    assert route_goal(goal) == "case_curator", f"{goal!r} 路由错位"


@pytest.mark.parametrize("goal", [
    "对通讯行业标杆企业做研究案例推演",
    "行业研究推演",
    "范式发动机跑一次",
    "benchmark study",
])
def test_research_intents_still_route_to_industry_research(goal):
    assert route_goal(goal) == "industry_research", f"{goal!r} 路由错位"


@pytest.mark.asyncio
async def test_list_intent_actually_hits_list_cases():
    """路由 + 执行链路整体验证：列举意图返回 case_count/cases 而非单案例推演。"""
    from src.runtime.agent.router import execute_by_agent

    agent = route_goal("列出所有研究案例")
    result = await execute_by_agent(agent, "列出所有研究案例")
    assert "case_count" in result and result["case_count"] >= 4
    assert isinstance(result.get("cases"), list)
    _assert_no_leak(result, "case_curator 列表")


# ───────────────────────── #427 REST ─────────────────────────


@pytest.mark.asyncio
async def test_presets_library_api(async_client_admin):
    r = await async_client_admin.get("/presets/library")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["equipment"]["industry_count"] >= 3
    assert d["equipment"]["profile_count"] >= 15
    assert d["erp"]["count"] >= 7
    assert d["mes"]["count"] >= 4
    codes = {i["industry"] for i in d["equipment"]["industries"]}
    assert {"semiconductor", "3c", "new_energy"} <= codes


@pytest.mark.asyncio
async def test_presets_industry_detail_api(async_client_admin):
    r = await async_client_admin.get("/presets/library/semiconductor")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["profile_count"] >= 9
    assert d["equipments"][0]["opcua_tags"]
    bad = await async_client_admin.get("/presets/library/not_an_industry")
    assert bad.status_code == 404


@pytest.mark.asyncio
async def test_cases_library_api_anonymous(async_client_admin):
    r = await async_client_admin.get("/cases/library")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["case_count"] >= 4
    _assert_no_leak(d, "GET /cases/library")

    cid = d["cases"][0]["case_id"]
    r2 = await async_client_admin.get(f"/cases/library/{cid}")
    assert r2.status_code == 200, r2.text
    _assert_no_leak(r2.json(), f"GET /cases/library/{cid}")
    assert "real_anchor" not in r2.json()["case"]

    r3 = await async_client_admin.get("/cases/library/case_not_exist")
    assert r3.status_code == 404


# ───────────────────────── #428 入驻接设备预设 ─────────────────────────


@pytest.mark.asyncio
async def test_onboarding_includes_equipment_presets():
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent
    from src.runtime.enterprise_store import profile_store

    tid = "t_eq_preset_case"
    profile_store.upsert(tid, {
        "industry": "半导体", "region": "上海", "org_scale": "1000+",
        "systems": {"erp": "SAP", "mes": "自有", "gateway": ["OPC-UA"], "social": [], "knowledge_base": False},
        "intent": {"free_tier_ok": True, "internal_connect": "现在就开", "concerns": ""},
        "narrative": "",
    })
    res = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=tid)
    eq = res["equipment_presets"]
    assert eq["matched"] is True
    assert eq["industry_code"] == "semiconductor"
    assert eq["profile_count"] >= 9
    assert eq["equipments"][0]["equipment_id"]
    _assert_no_leak(res, "enterprise_onboarding 推荐")


@pytest.mark.asyncio
async def test_onboarding_industry_without_preset_degrades():
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent
    from src.runtime.enterprise_store import profile_store

    tid = "t_eq_preset_none"
    profile_store.upsert(tid, {
        "industry": "光伏", "region": "", "org_scale": "",
        "systems": {}, "intent": {"internal_connect": "暂不"}, "narrative": "",
    })
    res = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=tid)
    assert res["equipment_presets"]["matched"] is False
    assert res["equipment_presets"]["profile_count"] == 0


# ───────────────────────── #429 研究案例租户 ─────────────────────────


@pytest.mark.asyncio
async def test_seed_case_tenants_idempotent():
    from src.runtime.seed_case_tenants import CASE_TENANTS, seed_case_tenants
    from src.runtime.tenant_store import tenant_store

    await tenant_store.init()
    first = await seed_case_tenants()
    assert len(first["tenants"]) == 2
    for spec in CASE_TENANTS:
        assert tenant_store.get(spec["tenant_id"]) is not None
    # 幂等：二次调用不再新建
    second = await seed_case_tenants()
    assert all(t["created"] is False for t in second["tenants"])


def test_case_tenant_names_are_anonymous():
    from src.runtime.seed_case_tenants import CASE_TENANTS

    _assert_no_leak(CASE_TENANTS, "CASE_TENANTS 定义")
    for spec in CASE_TENANTS:
        assert "未签约" in spec["tenant_name"], "租户名须标注未签约，避免冒充客户"


@pytest.mark.asyncio
async def test_case_tenant_binding_maps_to_existing_cases():
    from src.agents.case_curator.agent import case_curator_agent
    from src.runtime.seed_case_tenants import TENANT_CASE_BINDING

    case_curator_agent._ensure_seed()
    for tid, cid in TENANT_CASE_BINDING.items():
        assert case_curator_agent._get_case(cid) is not None, f"{tid} 绑定案例 {cid} 不存在"


@pytest.mark.asyncio
async def test_cases_my_unbound_tenant_returns_bound_false(async_client_admin):
    r = await async_client_admin.get("/cases/my")
    assert r.status_code == 200, r.text
    d = r.json()
    # 默认 admin 属于 default 租户，未绑定案例
    assert d["bound"] is False or d["case"]["case_id"].startswith("case_")
    _assert_no_leak(d, "GET /cases/my")


# ───────────────────────── #439 质量审计回归（3 个字段错位 Bug）─────────────────────────


@pytest.mark.asyncio
async def test_presets_library_coverage_is_dict(async_client_admin):
    """Bug 2 回归：/presets/library 的 coverage 必须是 dict（前端按分段渲染）。
    若被误标为 string 直接渲染，React 会抛 Objects are not valid as a React child → 整页白屏。
    """
    r = await async_client_admin.get("/presets/library")
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d["coverage"], dict), "coverage 必须是 dict（er/mes/equipment/permission 分段）"
    for k in ("erp", "mes", "equipment", "permission"):
        assert k in d["coverage"], f"coverage 缺字段 {k}"
        assert isinstance(d["coverage"][k], str) and d["coverage"][k], f"coverage.{k} 应为非空文本"


@pytest.mark.asyncio
async def test_presets_industry_detail_keyparts_are_dicts(async_client_admin):
    """Bug 3 回归：/presets/library/{industry} 的 key_parts 必须是 list[dict]（含 name 字段）。
    若前端按 string[] 渲染会显示 [object Object]。
    """
    r = await async_client_admin.get("/presets/library/semiconductor")
    assert r.status_code == 200, r.text
    d = r.json()
    for eq in d["equipments"]:
        assert isinstance(eq["key_parts"], list), "key_parts 必须是 list"
        for kp in eq["key_parts"]:
            assert isinstance(kp, dict), "key_parts 元素必须是 dict"
            assert "name" in kp and isinstance(kp["name"], str), "key_parts 元素须含 name 文本"


@pytest.mark.asyncio
async def test_cases_my_bound_tenant_nests_case(async_client_admin):
    """Bug 1 回归：绑定租户 GET /cases/my 必须把案例数据嵌套在 case 字段下；
    disclosure_facts / derived_insights 在 case 内（前端须读 myCase.case.* 而非顶层）。
    """
    from httpx import ASGITransport, AsyncClient

    from src.runtime.authn.security import encode_jwt
    from src.runtime.main import app
    from src.runtime.seed_case_tenants import TENANT_CASE_BINDING

    bound_tid = next(iter(TENANT_CASE_BINDING))  # telecom / semicon
    token = encode_jwt({"sub": "lib_audit", "role": "TENANT_ADMIN", "tenant_id": bound_tid})
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        r = await c.get("/cases/my")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["bound"] is True, "绑定租户须返回 bound=true"
        assert "case" in d, "绑定案例须嵌套在 case 字段下"
        cse = d["case"]
        assert isinstance(cse.get("subject_anon"), str) and cse["subject_anon"], "case.subject_anon 必填"
        assert "disclosure_facts" in cse, "disclosure_facts 须在 case 内"
        assert "derived_insights" in cse, "derived_insights 须在 case 内"
        assert isinstance(cse["derived_insights"], list)
        _assert_no_leak(d, "GET /cases/my 绑定租户")
