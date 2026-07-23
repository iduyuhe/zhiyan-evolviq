"""Agent执行会话与审计日志"""

import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, Float, String, Text, UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base, TimestampMixin


class SessionStatus(str, enum.Enum):
    planning = "planning"        # Agent正在规划
    awaiting_approval = "awaiting_approval"  # 等待人确认
    executing = "executing"      # 正在执行
    completed = "completed"      # 执行完成
    rejected = "rejected"        # 人被驳回
    failed = "failed"           # 执行失败
    intervened = "intervened"   # 人中途介入


class AgentSession(Base, TimestampMixin):
    """Agent执行会话"""
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    user_id: Mapped[str] = mapped_column(String(128), default="anonymous")
    goal: Mapped[str] = mapped_column(Text)  # 自然语言目标
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)  # Agent生成的规划（JSON/Markdown）
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.planning)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # 执行结果摘要
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_boundary_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditLog(Base):
    """审计日志"""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)  # goal_set, plan_created, approved, executed, rejected, intervened
    actor: Mapped[str] = mapped_column(String(64))  # human / agent_name
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
