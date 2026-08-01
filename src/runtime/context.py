"""请求级租户上下文（多租户隔离的单一真相来源）。

历史问题：租户隔离长期"软"落地——`require_auth` 返回 `tenant_id` 但各处理器
常忽略它，转而信任请求体 / Query 的 `tenant` 字段（客户端可任意指定），
导致跨租户读写泄漏。

修复策略（S2 对外前必须）：
- `require_auth` 在鉴权后调用 `set_current_tenant(u["tenant_id"])`，把租户钉死在请求上下文。
- 所有写 / 读端点统一通过 `get_current_tenant()` 取租户，丢弃客户端传入的 tenant。
- 仅 SUPERADMIN 可在显式传参时跨租户查看（受 `require_role` 保护）。

注意：contextvar 在每个请求 task 内有独立副本，请求结束即失效，无需手动 reset
（MCP 联邦 dispatch 内部仍用 try/finally reset 以恢复调用前上下文）。
"""
import contextvars
from typing import Any

current_tenant: contextvars.ContextVar = contextvars.ContextVar("zhiyan_tenant", default="default")

#: 权限第③层——当前请求用户的功能作用域（business_role + capability_scope）。
#: 默认 None = 不限制（向后兼容：既有匿名/存量用户行为不变）。
current_capability: contextvars.ContextVar = contextvars.ContextVar(
    "zhiyan_capability", default=None
)


def get_current_tenant() -> str:
    """读取当前请求所属租户（handler / 工具内可用）。"""
    return current_tenant.get()


def set_current_tenant(tenant_id: str) -> contextvars.Token:
    return current_tenant.set(tenant_id or "default")


def get_current_capability() -> dict[str, Any] | None:
    """读取当前请求用户的功能作用域快照。

    返回形如 ``{"username":..., "business_role":..., "capability_scope": {...}}``；
    None 表示未设置（不限制）。
    """
    return current_capability.get()


def set_current_capability(cap: dict[str, Any] | None) -> contextvars.Token:
    """把功能作用域钉在请求上下文（由鉴权依赖统一调用，业务层只读）。"""
    return current_capability.set(cap)
