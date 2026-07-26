"""FastAPI 依赖——从 Authorization: Bearer <JWT> 解析当前用户 + 角色门禁

用法：
    @router.get("/me")
    async def me(u: dict = Depends(get_current_user)):
        ...

    @router.delete("/users/{uid}")
    async def del_user(u: dict = Depends(require_role("superadmin"))):
        ...   # 角色不足自动 403
"""

from fastapi import Depends, Header, HTTPException

from src.runtime.authn.config import config
from src.runtime.authn.roles import parse_role
from src.runtime.authn.service import authn_service


async def get_current_user(authorization: str = Header(None, alias="Authorization")) -> dict:
    """解析 Bearer JWT；缺失/无效 → 401。返回用户档案 dict。"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头（Bearer JWT）")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authorization 格式须为 Bearer <token>")
    user = authn_service.get_user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="JWT 无效或已过期")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="账号已停用")
    return user


def require_role(min_role: str):
    """角色门禁依赖工厂：当前用户角色 rank >= min_role 才放行，否则 403。"""

    async def _guard(u: dict = Depends(get_current_user)) -> dict:
        if not authn_service.check_role(u.get("role", "OPERATOR"), min_role):
            from src.runtime.authn.roles import role_label

            need = role_label(min_role)
            got = role_label(u.get("role", "OPERATOR"))
            raise HTTPException(status_code=403, detail=f"权限不足：需要 {need}，当前 {got}")
        return u

    return _guard


async def require_auth(
    authorization: str = Header(None, alias="Authorization"),
    x_tenant_key: str = Header(None, alias="X-Tenant-Key"),
) -> dict | None:
    """全局鉴权依赖（可配置强制）。

    - ZHIYAN_AUTH_REQUIRE=1（生产）：等同 get_current_user，缺失/无效 JWT → 401/403。
    - 未开启（开发/测试默认）：不强制。若请求带有效 Bearer 则解析返回，
      否则返回匿名上下文（tenant 取自 X-Tenant-Key 或 default），保证既有测试与
      不带 token 的 e2e 脚本继续可用。
    """
    if not config.REQUIRE_AUTH:
        if authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer" and token:
                u = authn_service.get_user_from_token(token)
                if u is not None:
                    return u
        return {
            "username": "anonymous",
            "role": "SUPERADMIN",
            "tenant_id": x_tenant_key or "default",
            "auth_source": "local",
        }
    # 强制模式：严格校验
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头（Bearer JWT）")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authorization 格式须为 Bearer <token>")
    user = authn_service.get_user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="JWT 无效或已过期")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="账号已停用")
    return user
