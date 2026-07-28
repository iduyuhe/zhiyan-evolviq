"""S3-1 行为埋点基座——通用行为事件 ORM 模型（#315）

设计要点（呼应 MASTER §S3 四层推荐体系 + 隐私边界）：
- 通用事件池：一张 behavior_events 表承载全部行为信号（信号查看/拉取、agent 会话、
  解读、反馈……），event_type 开放扩展，为 S3 层1-4 与共生进化环统一供血。
- 🔴 隐私红线：行为画像仅存于本租户、仅用于本租户推荐，绝不跨租户聚合到
  个体可识别粒度；所有读写按 tenant_id 过滤（fail-closed）。
- 韧性同构：内存权威 + DB best-effort（behavior_store 负责），db 不可达自动降级。
- meta 为 JSON 文本（SQLite/PG 双兼容），只存轻量上下文（如 goal 前 80 字、
  信号 kind），绝不存 PII / 原始业务数据。
"""

import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base, TimestampMixin

# 预置事件类型（开放扩展：record() 不强校验枚举，仅规整小写）
BE_SIGNAL_VIEW = "signal_view"        # 查看环境信号流（前端信号查看钩子）
BE_SIGNAL_PULL = "signal_pull"        # 手动拉取信号
BE_AGENT_SESSION = "agent_session"    # 发起 agent 会话（单/快检/多编排）
BE_INSIGHT_VIEW = "insight_view"      # 查看平台建议（platform_insight）
BE_FEEDBACK = "feedback_submit"       # 提交反馈（共生环）


class BehaviorEvent(Base, TimestampMixin):
    """行为事件——S3 推荐体系的第一手燃料"""

    __tablename__ = "behavior_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # username（本租户内可识别）
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    # 行为对象：kind（signal/agent/source/insight/...）+ id（agent 名/源名/信号 id）
    object_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 轻量上下文（JSON 文本；绝不存 PII / 原始业务数据）
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "object_kind": self.object_kind,
            "object_id": self.object_id,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
