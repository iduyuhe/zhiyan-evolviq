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


class MetricsRecord(Base):
    """效果指标记录——支撑「效果报告 / 按效果调参」跨重启累积。

    与审计日志分离：本表存结构化的自主率/介入率信号，重启后回灌内存，
    使策略调参可基于历史效果而非每重启清零。
    """
    __tablename__ = "metrics_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # action / decision
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(String(256), default="")  # 人类可读短描述
    payload: Mapped[str] = mapped_column(Text)  # JSON 结构化明细
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FeedbackRecord(Base):
    """人类反馈经验——偏好/禁忌记忆的持久化。

    人类在介入中心审批/驳回 Agent 动作时写入；供策略自学习（反哺 suggest）
    与未来 P2 Prompt/RAG 自修订使用。租户隔离、按 agent 索引便于按 Agent 召回。
    """

    __tablename__ = "feedback_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    agent: Mapped[str] = mapped_column(String(64), index=True)  # 被反馈的 Agent
    action_type: Mapped[str] = mapped_column(String(64), default="")  # 动作类型（如 lock_material）
    decision: Mapped[str] = mapped_column(String(16), index=True)  # approved / rejected
    context: Mapped[str] = mapped_column(Text, default="")  # 触发场景/目标摘要
    note: Mapped[str] = mapped_column(String(512), default="")  # 人类批注
    source: Mapped[str] = mapped_column(String(32), default="intervention")  # 反馈来源
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PromptVersion(Base):
    """Prompt 版本库——P2 自进化：LLM/启发式复盘失败案例生成的候选 system prompt。

    版本化 + 人工审批门（绝不直接应用）：proposed → approved → active，
    active 版本可热替换 live Agent 单例的 system_prompt，并支持一键回滚。
    租户隔离、按 agent 索引。
    """

    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    agent: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(default=1)
    content: Mapped[str] = mapped_column(Text)  # 候选/生效的完整 system prompt
    parent_version: Mapped[int | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(16), default="proposed", index=True)  # proposed/approved/active/rejected
    proposer: Mapped[str] = mapped_column(String(16), default="llm")  # llm/heuristic/human
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    applied_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class KgFactProposal(Base):
    """知识图谱事实提议——P2 自进化 RAG 自更新：从结构化产出抽取的事实候选。

    经人工审批后 upsert 进 Neo4j 知识图谱（Entity 节点 + 关系边），提升后续 RAG 检索质量。
    事实锚点铁律：仅写实体/关系，绝不改写业务数字。
    """

    __tablename__ = "kg_fact_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    agent: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(String(256))   # 头实体节点 id（如 MAT:XYZ）
    predicate: Mapped[str] = mapped_column(String(128))  # 关系（如 可替代/导致/依赖）
    object_val: Mapped[str] = mapped_column(String(256))  # 尾实体节点 id
    source: Mapped[str] = mapped_column(String(256), default="")  # 事实来源描述
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)  # draft/approved
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
