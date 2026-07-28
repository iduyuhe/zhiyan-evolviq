"""共生进化环——客户反馈 ORM 模型

设计要点（呼应 §3.6 共生进化环 + 红线）：
- 反馈租户隔离：所有反馈带 tenant_id，读写按 tenant 过滤，绝不跨租户可见。
- 审核门（_needs_review 同构）：反馈经自动脱敏 + 人工审核（escalate）后才转为
  开源 GitHub Issue（标签 from-customer）。未脱敏、未审核的反馈绝不出内网。
- 48h 首响应 SLA：first_response_due_at = created_at + 48h；responded_at 在
  平台首次回音（escalate / 人工响应）时写入，用于看板度量。
- 敏感字段（github_issue_url / desensitized_text）只在内网 + 脱敏后产物，
  不出租户边界。
"""

import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base, TimestampMixin

# 反馈类型
FB_LIKE = "like"      # 👍 有用
FB_DISLIKE = "dislike"  # 👎 不准
FB_IDEA = "idea"      # 💡 我有想法

# 处理状态（_needs_review 同构语义）
FB_RECEIVED = "received"          # 已收到，待审核
FB_PENDING_REVIEW = "pending_review"  # 审核中（已脱敏、待提报）
FB_ISSUED = "issued"              # 已提报开源 Issue
FB_REJECTED = "rejected"          # 已驳回（仅内部闭环，不出内网）


class Feedback(Base, TimestampMixin):
    """客户反馈——共生进化环的第一推动力"""

    __tablename__ = "feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 提交者 username
    feedback_type: Mapped[str] = mapped_column(String(16))  # like/dislike/idea
    target_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)  # signal/agent_conclusion/other
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default=FB_RECEIVED)
    # 脱敏后文本（提报 Issue 用，剥离租户名/PII/业务数据）
    desensitized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 开源 Issue 回链（仅 issued 后有值）
    github_issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    reviewer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 48h SLA：首次回音截止 = created_at + 48h（ISO）
    first_response_due_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 平台首次回音时刻（escalate / 人工响应写入）
    responded_at: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def to_dict(self, include_internal: bool = False) -> dict:
        d = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "feedback_type": self.feedback_type,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "text": self.text,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "first_response_due_at": self.first_response_due_at,
            "responded_at": self.responded_at,
            "github_issue_url": self.github_issue_url,
            "github_issue_number": self.github_issue_number,
        }
        if include_internal:
            d["desensitized_text"] = self.desensitized_text
            d["reviewer"] = self.reviewer
        return d
