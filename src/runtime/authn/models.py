"""用户 ORM 模型——企业认证的用户表（users）

与多租户体系对齐：每个用户归属一个 tenant_id（联合 tenants 表）。
auth_source 记录来源（local / ldap / oauth2 / saml），便于审计与混合登录。
密码仅存 PBKDF2 哈希（见 security.hash_password），明文绝不落库。
"""

import uuid

from sqlalchemy import Boolean, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.authn.roles import Role
from src.runtime.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # PBKDF2 哈希；LDAP/OAuth2 用户可留空（凭证不在本地）
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.OPERATOR)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    auth_source: Mapped[str] = mapped_column(String(16), default="local")  # local/ldap/oauth2/saml
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 外部目录中的唯一标识（LDAP dn / OAuth2 sub），用于去重同步
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    def to_dict(self, include_secrets: bool = False) -> dict:
        d = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.name,
            "role_label": self.role.name,
            "tenant_id": self.tenant_id,
            "auth_source": self.auth_source,
            "is_active": self.is_active,
            "external_id": self.external_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_secrets:
            d["password_hash"] = self.password_hash
        return d
