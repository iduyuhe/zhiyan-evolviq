"""API 依赖——从请求头解析当前租户

多租户接入的「薄切面」：所有需要隔离的路由用 `Depends(get_tenant)` 注入 tenant_id。

解析优先级（2026-08-01 修：登录用户不再回落 default 租户）：
1. 已登录且归属真实租户（tenant_id != default）且非 superadmin → **JWT 租户恒定生效**，
   忽略 X-Tenant-Key（企业用户被钉在自己企业里，不会因浏览器里残留的旧租户 Key 串台）；
2. 否则若带 X-Tenant-Key → 按密钥解析（平台侧 superadmin / default 用户的租户切换器照旧可用）；
3. 否则若已登录 → 取 JWT 的 tenant_id；
4. 全都没有 → 默认租户 `default`（匿名调用与集成测试行为不变）。
"""

from fastapi import Header, HTTPException

from src.runtime.models.tenant import DEFAULT_TENANT_ID
from src.runtime.tenant_store import tenant_store

# 平台管理员密钥（用于列出/管理全部租户）。从环境变量读取；未配置则平台管理接口不可用。
import os

PLATFORM_ADMIN_KEY = os.getenv("TENANT_ADMIN_KEY", "")


def _user_from_bearer(authorization: str | None) -> dict | None:
    """尽力从 Authorization 头解析用户；任何异常/无效 token 一律返回 None（绝不抛错）。

    真正的 401/403 由全局 `require_auth` 依赖负责，这里只做「租户归属」的补充判定，
    保持 fail-open 以免影响匿名与存量调用链路。
    """
    if not authorization:
        return None
    try:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        from src.runtime.authn.service import authn_service

        return authn_service.get_user_from_token(token)
    except Exception:  # noqa: BLE001
        return None


async def get_tenant(
    x_tenant_key: str = Header(None, alias="X-Tenant-Key"),
    authorization: str = Header(None, alias="Authorization"),
) -> str:
    """解析当前租户（优先级见模块 docstring）。X-Tenant-Key 有头但无效 → 401。"""
    user = _user_from_bearer(authorization)
    if user:
        utid = (user.get("tenant_id") or "").strip()
        is_super = str(user.get("role", "")).lower() == "superadmin"
        # ① 企业用户钉死在自身租户：忽略任何 X-Tenant-Key，防止跨租户串台
        if utid and utid != DEFAULT_TENANT_ID and not is_super:
            return utid

    if x_tenant_key:
        tid = await tenant_store.resolve(x_tenant_key)
        if tid is None:
            raise HTTPException(status_code=401, detail="无效或已失效的租户密钥（X-Tenant-Key）")
        return tid

    if user and (user.get("tenant_id") or "").strip():
        return user["tenant_id"].strip()
    return DEFAULT_TENANT_ID


async def get_platform_admin(x_admin_key: str = Header(None, alias="X-Platform-Admin-Key")) -> str:
    """平台管理员鉴权（用于列出租户/强制删除）。未配置 TENANT_ADMIN_KEY 则返回 403。"""
    if not PLATFORM_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="平台未启用管理员密钥（TENANT_ADMIN_KEY 未配置）")
    if x_admin_key != PLATFORM_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="平台管理员密钥错误")
    return "platform-admin"
