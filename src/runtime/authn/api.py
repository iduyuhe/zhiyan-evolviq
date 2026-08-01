"""企业认证 API——登录 / 当前用户 / 用户管理 / 后端状态 / OAuth2 回调

路由前缀 /authn（与现有 /auth 授权边界互不冲突）。
说明：
- 所有写操作（建用户/改角色）受 require_role 保护，未登录 → 401，角色不足 → 403。
- 现有 API Key 多租户体系（X-Tenant-Key）保持不变；JWT 是「用户身份」层，
  与「租户」层正交，后续受保护路由可同时注入 get_current_user + get_tenant。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from src.runtime.authn import backends
from src.runtime.authn.config import config
from src.runtime.authn.deps import get_current_user, require_role
from src.runtime.authn.service import authn_service

router = APIRouter(prefix="/authn", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "operator"
    tenant_id: str = "default"
    email: str | None = None
    display_name: str | None = None
    # 权限第③层：业务角色（只填岗位即自动套用权限模板库的标准作用域）
    business_role: str | None = None
    capability_scope: dict | None = None


class SetRoleRequest(BaseModel):
    role: str


class SetCapabilityRequest(BaseModel):
    """权限第③层设置：只填 business_role 即按模板配权；也可手工传 capability_scope。"""

    business_role: str | None = None
    capability_scope: dict | None = None
    industry: str | None = None


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """用户名 + 密码登录（本地优先，自动回退 LDAP）。成功返回 JWT。

    v28.3：登录失败上报监控器（滑动窗口内超阈值 → 暴力破解告警进 UNS system 路）。
    """
    result = await authn_service.authenticate(req.username, req.password)
    if not result:
        try:  # 韧性：监控上报失败绝不影响登录主流程
            from src.runtime.monitoring import alert_monitor
            client_ip = request.client.host if request.client else ""
            alert_monitor.record_login_failure(req.username, ip=client_ip)
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="用户名或密码错误（本地与目录均拒绝）")
    try:
        from src.runtime.monitoring import alert_monitor
        alert_monitor.record_login_success(req.username)
    except Exception:
        pass
    return result


@router.get("/me")
async def me(u: dict = Depends(get_current_user)):
    """返回当前登录用户信息。"""
    return {"user": u}


@router.get("/backends")
async def backend_status(_: dict = Depends(get_current_user)):
    """返回各认证后端配置状态（便于客户 IT 自查对接）。"""
    return {
        "local": {"enabled": True, "label": "本地账号"},
        "ldap": {
            "enabled": config.LDAP_ENABLED or config.LDAP_MOCK,
            "mock": config.LDAP_MOCK,
            "server": config.LDAP_SERVER or ("(mock)" if config.LDAP_MOCK else ""),
            "label": "企业 AD/LDAP",
        },
        "oauth2": {"enabled": config.OAUTH_ENABLED, "label": "OAuth2 / OIDC"},
        "saml": {"enabled": False, "label": "SAML 2.0（可扩展）"},
    }


@router.get("/users")
async def list_users(
    tenant_id: str | None = Query(None),
    _: dict = Depends(require_role("tenant_admin")),
):
    """列出用户（租户管理员及以上）。"""
    users = await authn_service.list_users(tenant_id)
    return {"total": len(users), "users": users}


@router.post("/users")
async def create_user(req: CreateUserRequest, _: dict = Depends(require_role("tenant_admin"))):
    """创建用户（租户管理员及以上）。"""
    try:
        rec = await authn_service.create_user(
            username=req.username,
            password=req.password,
            role=req.role,
            tenant_id=req.tenant_id,
            email=req.email,
            display_name=req.display_name,
            business_role=req.business_role,
            capability_scope=req.capability_scope,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"status": "created", "user": rec}


@router.get("/business-roles")
async def list_business_roles(
    industry: str | None = Query(None, description="行业 key，命中则返回行业专属作用域"),
    _: dict = Depends(get_current_user),
):
    """列出权限模板库中的标准岗位（前端「用户权限」下拉框用）。"""
    from src.presets.permission_templates import (
        list_business_roles as _roles,
        list_industries,
        scope_for_business_role,
    )

    roles = _roles()
    for r in roles:
        r["scope"] = scope_for_business_role(r["value"], industry=industry)
    return {
        "total": len(roles),
        "industry": industry,
        "industries": list_industries(),
        "roles": roles,
    }


@router.post("/users/{user_id}/capability")
async def set_capability(
    user_id: str,
    req: SetCapabilityRequest,
    _: dict = Depends(require_role("tenant_admin")),
):
    """设置用户的业务角色 / 功能作用域（权限第③层，租户管理员及以上）。

    - 传 business_role 不传 capability_scope → 自动套用权限模板库标准作用域；
    - business_role 传空串 → 清空限制（恢复全部智能体可见）。
    """
    try:
        rec = await authn_service.set_capability(
            user_id,
            business_role=req.business_role,
            capability_scope=req.capability_scope,
            industry=req.industry,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated", "user": rec}


@router.get("/my-agents")
async def my_agents(u: dict = Depends(get_current_user)):
    """返回当前用户实际可见的智能体列表（前端菜单渲染的唯一真相源）。"""
    from src.runtime.api.agents_api import AGENT_REGISTRY
    from src.runtime.authn.capability import (
        business_role_label,
        is_agent_read_only,
        is_unrestricted,
        visible_agents,
    )

    scope = u.get("capability_scope")
    all_ids = [a["id"] for a in AGENT_REGISTRY]
    allowed = set(visible_agents(scope, all_ids))
    items = [
        {**a, "read_only": is_agent_read_only(scope, a["id"])}
        for a in AGENT_REGISTRY
        if a["id"] in allowed
    ]
    return {
        "business_role": u.get("business_role"),
        "business_role_label": business_role_label(u.get("business_role")),
        "unrestricted": is_unrestricted(scope),
        "total": len(items),
        "agents": items,
    }


@router.post("/users/{user_id}/role")
async def set_role(user_id: str, req: SetRoleRequest, _: dict = Depends(require_role("superadmin"))):
    """变更用户角色（仅超级管理员）。"""
    try:
        rec = await authn_service.set_role(user_id, req.role)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "updated", "user": rec}


@router.get("/oauth/login")
async def oauth_login():
    """跳转到 OAuth2 授权端点（Azure AD / 企业微信 / 飞书 / Keycloak）。"""
    url = authn_service._oauth.authorize_url()
    if not url:
        raise HTTPException(status_code=404, detail="OAuth2 未配置（设置 OAUTH_* 环境变量启用）")
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url)


@router.get("/oauth/callback")
async def oauth_callback(code: str = Query(...), state: str = Query("zhiyan")):
    """OAuth2 回调：用 code 换取用户并签发 JWT，重定向回前端（token 带入 query）。"""
    result = await authn_service.authenticate_oauth_code(code)
    if not result:
        raise HTTPException(status_code=401, detail="OAuth2 登录失败")
    from fastapi.responses import RedirectResponse

    return RedirectResponse(f"/?token={result['access_token']}")
