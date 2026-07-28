"""环境感知订阅规则模型（S2 v30.5 β —— 无感转型外圈地基）

「抓取共享、语义隔离」两层制（ENVIRONMENT_PERCEPTION_PLAN §3.5）的第二层：
- 第一层：原始外部信号平台级抓一次（env_sources/*，无租户私有信息）。
- 第二层（本表）：每个租户用自己的订阅规则从平台信号池中筛选可见流，
  规则严格 tenant-scoped，推荐画像绝不跨租户。

规则维度（β1 筛选规则模型）：
- source_name   ：订阅哪个源（policy / market / benchmark，未来可扩）。
- enabled       ：源开关（β4 成本开关的租户侧）。
- credibility_min：准入阈值——official > authoritative > general（F4 可信治理）。
- keywords_include / keywords_exclude：关键词过滤（JSON 数组字符串）。
- poll_interval_sec：期望轮询频率（成本开关；平台侧取所有租户最小值执行）。

免费额度（总纲 §3 S2-3）：免费租户最多启用 3 个信息源——上限校验在
env_subscription_store.upsert() 做（表层不做，保持模型纯粹）。
"""

import uuid

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base, TimestampMixin

# credibility 序：数值越大越可信（准入阈值比较用）
CRED_RANK = {"official": 3, "authoritative": 2, "general": 1}


class EnvSubscription(Base, TimestampMixin):
    """租户 × 环境源 订阅规则（一租户对多源，一源一行）"""

    __tablename__ = "env_subscriptions"
    __table_args__ = (UniqueConstraint("tenant_id", "source_name", name="uq_env_sub_tenant_source"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    source_name: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 准入阈值：只接收 credibility >= 此级的信号（默认 general = 全收，审核门在锚定层）
    credibility_min: Mapped[str] = mapped_column(String(32), default="general")
    # 关键词过滤（JSON 数组字符串；include 空 = 不过滤）
    keywords_include: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords_exclude: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 期望轮询频率（秒）；平台侧执行取全租户最小值
    poll_interval_sec: Mapped[int] = mapped_column(Integer, default=3600)

    def to_dict(self) -> dict:
        import json

        def _loads(v):
            if not v:
                return []
            try:
                out = json.loads(v)
                return out if isinstance(out, list) else []
            except Exception:
                return []

        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "source_name": self.source_name,
            "enabled": self.enabled,
            "credibility_min": self.credibility_min,
            "keywords_include": _loads(self.keywords_include),
            "keywords_exclude": _loads(self.keywords_exclude),
            "poll_interval_sec": self.poll_interval_sec,
            "updated_at": self.updated_at.isoformat() if getattr(self, "updated_at", None) else None,
        }
