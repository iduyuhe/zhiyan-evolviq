"""企业认证包（authn）—— 与现有 /auth 授权边界(authorization)区分

提供：用户/角色/租户三层 + JWT + LDAP/OAuth2 后端 + RBAC 依赖。
"""

from src.runtime.authn import backends, config, deps, models, roles, security, service
from src.runtime.authn.service import authn_service

__all__ = [
    "authn_service",
    "backends",
    "config",
    "deps",
    "models",
    "roles",
    "security",
    "service",
]
