"""API 依赖——从请求头解析当前租户

多租户接入的「薄切面」：所有需要隔离的路由用 `Depends(get_tenant)` 注入 tenant_id。
未携带 X-Tenant-Key 时回退到默认租户 `default`，保证现有匿名调用与集成测试行为不变。
"""

from fastapi import Header, HTTPException

from src.runtime.models.tenant import DEFAULT_TENANT_ID
from src.runtime.tenant_store import tenant_store

# 平台管理员密钥（用于列出/管理全部租户）。从环境变量读取；未配置则平台管理接口不可用。
import os

PLATFORM_ADMIN_KEY = os.getenv("TENANT_ADMIN_KEY", "")


async def get_tenant(x_tenant_key: str = Header(None, alias="X-Tenant-Key")) -> str:
    """解析当前租户。无头 → 默认租户；有头但无效 → 401。"""
    if not x_tenant_key:
        return DEFAULT_TENANT_ID
    tid = await tenant_store.resolve(x_tenant_key)
    if tid is None:
        raise HTTPException(status_code=401, detail="无效或已失效的租户密钥（X-Tenant-Key）")
    return tid


async def get_platform_admin(x_admin_key: str = Header(None, alias="X-Platform-Admin-Key")) -> str:
    """平台管理员鉴权（用于列出租户/强制删除）。未配置 TENANT_ADMIN_KEY 则返回 403。"""
    if not PLATFORM_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="平台未启用管理员密钥（TENANT_ADMIN_KEY 未配置）")
    if x_admin_key != PLATFORM_ADMIN_KEY:
        raise HTTPException(status_code=401, detail="平台管理员密钥错误")
    return "platform-admin"
