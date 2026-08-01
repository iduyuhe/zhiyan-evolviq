"""权限第③层（业务角色 + 功能作用域）测试

覆盖 PRD `docs/PERMISSION_ARCHITECTURE_PRD.md` 的 7 条验收用例：
1. 默认（NULL 作用域）全放行——存量用户零感知
2. 岗位模板收窄——设备工程师看不到成本分析
3. 引擎侧拦截——越权目标抛 CapabilityDenied
4. API 侧 403——越权调用返回 capability_denied
5. 只读作用域——自主动作强制转人工
6. JWT 往返——business_role / capability_scope 随 token 下发并解析
7. 权限模板库——岗位/行业模板可查、行业覆盖生效
"""

import pytest

from src.runtime.authn.capability import (
    BusinessRole,
    CapabilityDenied,
    business_role_label,
    ensure_agent_allowed,
    is_agent_allowed,
    is_agent_read_only,
    is_unrestricted,
    normalize_scope,
    visible_agents,
)
from src.presets.permission_templates import (
    GENERIC_TEMPLATES,
    industry_template,
    list_business_roles,
    list_industries,
    scope_for_business_role,
)


# ---------------------------------------------------------------- 1. 默认全放行


def test_null_scope_is_unrestricted():
    """NULL / 空 / 脏数据 → 全放行，绝不把存量用户锁死。"""
    for raw in (None, {}, [], "garbage", {"allowed_agents": []}):
        assert is_unrestricted(raw), f"{raw!r} 应归一为全放行"
        assert is_agent_allowed(raw, "cost_analysis")
        assert is_agent_allowed(raw, "任意不存在的agent")


def test_normalize_scope_shape():
    s = normalize_scope({"allowed_agents": ["a"], "read_only_agents": ["a"], "data_scope": {"x": 1}})
    assert set(s) == {"allowed_agents", "data_scope", "read_only_agents"}
    assert s["allowed_agents"] == ["a"]
    assert s["data_scope"] == {"x": 1}


# ---------------------------------------------------------------- 2. 岗位模板收窄


def test_device_engineer_cannot_see_cost_analysis():
    scope = scope_for_business_role(BusinessRole.DEVICE_ENGINEER.value)
    assert is_agent_allowed(scope, "pm_maintenance")
    assert not is_agent_allowed(scope, "cost_analysis")
    assert not is_unrestricted(scope)


def test_plant_manager_sees_everything():
    scope = scope_for_business_role(BusinessRole.PLANT_MANAGER.value)
    assert is_unrestricted(scope)
    assert is_agent_allowed(scope, "cost_analysis")


def test_visible_agents_filters():
    scope = scope_for_business_role(BusinessRole.SUPPLY_MANAGER.value)
    all_ids = ["supply_chain", "cost_analysis", "wms_logistics", "pm_maintenance"]
    vis = visible_agents(scope, all_ids)
    assert "supply_chain" in vis and "wms_logistics" in vis
    assert "cost_analysis" not in vis and "pm_maintenance" not in vis


# ---------------------------------------------------------------- 3. 引擎侧拦截


def test_ensure_agent_allowed_raises():
    scope = scope_for_business_role(BusinessRole.DEVICE_ENGINEER.value)
    ensure_agent_allowed("pm_maintenance", scope)  # 不抛
    with pytest.raises(CapabilityDenied) as ei:
        ensure_agent_allowed("cost_analysis", scope, BusinessRole.DEVICE_ENGINEER.value, "zhangsan")
    assert "cost_analysis" in str(ei.value)
    assert "设备工程师" in str(ei.value)


@pytest.mark.asyncio
async def test_engine_plan_blocked_by_capability():
    """引擎 plan() 在路由后即拦截越权目标。"""
    import uuid

    from src.runtime.agent.engine import AgentEngine
    from src.runtime.context import set_current_capability

    token = set_current_capability({
        "username": "dev_eng",
        "business_role": BusinessRole.DEVICE_ENGINEER.value,
        "capability_scope": scope_for_business_role(BusinessRole.DEVICE_ENGINEER.value),
    })
    try:
        engine = AgentEngine()
        with pytest.raises(CapabilityDenied):
            # 成本类目标会被 router 路由到 cost_analysis —— 设备工程师无权
            await engine.plan(str(uuid.uuid4()), "分析单位制造成本拆解与降本机会")
    finally:
        set_current_capability(None)
        token  # noqa: B018  上下文在测试结束即失效


@pytest.mark.asyncio
async def test_engine_plan_allowed_within_scope():
    """作用域内的目标正常放行。"""
    import uuid

    from src.runtime.agent.engine import AgentEngine
    from src.runtime.context import set_current_capability

    set_current_capability({
        "username": "dev_eng",
        "business_role": BusinessRole.DEVICE_ENGINEER.value,
        "capability_scope": scope_for_business_role(BusinessRole.DEVICE_ENGINEER.value),
    })
    try:
        engine = AgentEngine()
        sid = str(uuid.uuid4())
        plan = await engine.plan(sid, "检查设备健康状况与预测维护建议")
        assert isinstance(plan, str) and plan
        assert engine.get_session(sid)["agent"] == "pm_maintenance"
    finally:
        set_current_capability(None)


# ---------------------------------------------------------------- 4. 只读作用域


def test_read_only_agents_flagged():
    scope = scope_for_business_role(BusinessRole.FINANCE_CONTROLLER.value)
    assert is_agent_allowed(scope, "procurement_manage")
    assert is_agent_read_only(scope, "procurement_manage")
    assert not is_agent_read_only(scope, "cost_analysis")


# ---------------------------------------------------------------- 5. JWT 往返


def test_jwt_carries_capability():
    from src.runtime.authn.service import authn_service

    scope = scope_for_business_role(BusinessRole.QUALITY_MANAGER.value)
    issued = authn_service._issue({
        "username": "qm01",
        "id": "u-qm01",
        "role": "operator",
        "tenant_id": "dute",
        "business_role": BusinessRole.QUALITY_MANAGER.value,
        "capability_scope": scope,
    })
    back = authn_service.get_user_from_token(issued["access_token"])
    assert back["business_role"] == BusinessRole.QUALITY_MANAGER.value
    assert is_agent_allowed(back["capability_scope"], "quality_trace")
    assert not is_agent_allowed(back["capability_scope"], "supply_chain")
    assert issued["user"]["business_role_label"] == "质量经理"


def test_legacy_jwt_without_capability_is_unrestricted():
    """升级前签发的旧 token 无第③层字段 → 全放行，平滑过渡。"""
    from src.runtime.authn.security import encode_jwt
    from src.runtime.authn.service import authn_service

    old = encode_jwt({"sub": "legacy", "uid": "u1", "role": "OPERATOR", "tenant_id": "default"})
    u = authn_service.get_user_from_token(old)
    assert u["business_role"] is None
    assert is_unrestricted(u["capability_scope"])


# ---------------------------------------------------------------- 6. 权限模板库


def test_permission_template_registry():
    roles = list_business_roles()
    assert len(roles) == len(GENERIC_TEMPLATES) == 7
    assert {r["value"] for r in roles} == {r.value for r in BusinessRole}
    assert "semiconductor_fab" in list_industries()


def test_industry_override_applies():
    """半导体 Fab 的设备工程师额外可查良率（设备-良率强耦合）。"""
    generic = scope_for_business_role(BusinessRole.DEVICE_ENGINEER.value)
    fab = scope_for_business_role(BusinessRole.DEVICE_ENGINEER.value, industry="semiconductor_fab")
    assert not is_agent_allowed(generic, "yield_analysis")
    assert is_agent_allowed(fab, "yield_analysis")
    assert is_agent_read_only(fab, "yield_analysis")


def test_industry_template_full_map():
    tpl = industry_template("telecom_equipment")
    assert set(tpl) == {r.value for r in BusinessRole}
    assert is_agent_allowed(tpl[BusinessRole.SUPPLY_MANAGER.value], "industry_research")


def test_unknown_role_falls_back_to_unrestricted():
    assert is_unrestricted(scope_for_business_role("不存在的岗位"))
    assert business_role_label(None) == "未设置"


def test_preset_summary_includes_permission():
    from src.presets import get_preset_summary

    s = get_preset_summary()
    assert s["permission_role_count"] == 7
    assert "厂长/总经理" in s["permission_roles"]
    assert "permission" in s["estimated_coverage"]


# ---------------------------------------------------------------- 7. API 403


@pytest.mark.asyncio
async def test_api_returns_403_on_capability_denied():
    """越权调用 /sessions 返回 403 + capability_denied。"""
    import httpx
    from httpx import ASGITransport

    from src.runtime.authn.service import authn_service
    from src.runtime.main import app

    issued = authn_service._issue({
        "username": "dev_eng_api",
        "id": "u-dev-api",
        "role": "operator",
        "tenant_id": "default",
        "business_role": BusinessRole.DEVICE_ENGINEER.value,
        "capability_scope": scope_for_business_role(BusinessRole.DEVICE_ENGINEER.value),
    })
    headers = {"Authorization": f"Bearer {issued['access_token']}"}
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/sessions", json={"goal": "分析单位制造成本拆解与降本机会"}, headers=headers
        )
        assert r.status_code == 403, r.text
        body = r.json()
        assert body.get("error") == "capability_denied"
        assert body.get("agent") == "cost_analysis"

        # 作用域内目标应正常
        ok = await c.post(
            "/sessions", json={"goal": "检查设备健康状况与预测维护建议"}, headers=headers
        )
        assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_my_agents_endpoint_filters():
    import httpx
    from httpx import ASGITransport

    from src.runtime.authn.service import authn_service
    from src.runtime.main import app

    issued = authn_service._issue({
        "username": "sup_mgr",
        "id": "u-sup",
        "role": "operator",
        "tenant_id": "default",
        "business_role": BusinessRole.SUPPLY_MANAGER.value,
        "capability_scope": scope_for_business_role(BusinessRole.SUPPLY_MANAGER.value),
    })
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/authn/my-agents", headers={"Authorization": f"Bearer {issued['access_token']}"})
        assert r.status_code == 200, r.text
        body = r.json()
        ids = {a["id"] for a in body["agents"]}
        assert "supply_chain" in ids
        assert "cost_analysis" not in ids
        assert body["unrestricted"] is False
        assert body["business_role_label"] == "供应链经理"
