"""多租户核心模型——租户与密钥

设计要点（呼应「韧性降级」铁律）：
- 默认租户 `default` 始终存在，未携带 X-Tenant-Key 的请求自动归属它，
  因此现有匿名调用 / 集成测试在加多租户后行为不变。
- api_key 仅存 sha256 哈希，明文仅在「注册 / 轮换」时一次性返回，绝不落库。
- 行级隔离：所有业务表加 tenant_id 列，读写按 tenant 过滤（见 persistence / engine）。
- gateway_config 允许租户覆写工业协议网关连接参数；缺省则用平台共享网关。
"""

import hashlib
import secrets
import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base, TimestampMixin

DEFAULT_TENANT_ID = "default"


def hash_key(api_key: str) -> str:
    """计算 api_key 的 sha256 哈希（恒定长度，便于索引/比较）。"""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def gen_key() -> str:
    """生成一个新的明文租户密钥（仅注册/轮换时返回一次）。"""
    return secrets.token_urlsafe(24)


class Tenant(Base, TimestampMixin):
    """租户——一个企业/团队在平台上的隔离单元"""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    name: Mapped[str] = mapped_column(String(128))
    api_key_hash: Mapped[str] = mapped_column(String(64), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 工业协议网关连接参数覆写（JSON 字符串，缺省 None 表示用平台共享网关）
    gateway_config: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "has_gateway_config": bool(self.gateway_config),
        }
