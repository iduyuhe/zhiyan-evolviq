"""持久化服务——把 Agent 执行会话与审计日志落库（AgentSession + AuditLog）。

设计原则（呼应「事实锚点」铁律）：
1. 只落「会话元信息 + 确定性结果 JSON + 审计事件」，绝不改写 Agent 产出的任何数字/动作。
2. 优雅降级：db 不可用时所有方法静默 no-op；任何异常不外溢，绝不破坏确定性执行管道。
3. 异步优先：落库在引擎执行链路中以 await 提交，保证返回前数据已入库、可被查询。
4. 动态引用 db.async_session / db.db_available（configure_db 会重赋值模块全局，禁止快照）。
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from src.common import db
from src.runtime.models.agent_session import AgentSession, AuditLog, MetricsRecord, FeedbackRecord, SessionStatus, PromptVersion, KgFactProposal, TenantDataSource

logger = logging.getLogger(__name__)


def _safe_json(obj) -> str | None:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return None


def _is_uuid(v: str) -> bool:
    try:
        uuid.UUID(v)
        return True
    except Exception:
        return False


def _coerce_status(status: str) -> SessionStatus:
    try:
        return SessionStatus(status)
    except ValueError:
        return SessionStatus.executing


async def save_session(
    session_id: str,
    goal: str,
    *,
    plan: str | None = None,
    status: str = "planning",
    result: dict | None = None,
    error: str | None = None,
    auth_boundary_id: str | None = None,
    user_id: str = "anonymous",
    tenant_id: str = "default",
) -> None:
    """upsert AgentSession（以 session_id 为 PK）。db 不可用时静默跳过。"""
    if not db.db_available or db.async_session is None:
        return
    if not _is_uuid(session_id):
        return
    try:
        sid = uuid.UUID(session_id)
        async with db.async_session() as s:
            obj = await s.get(AgentSession, sid)
            if obj is None:
                obj = AgentSession(id=sid, tenant_id=tenant_id, user_id=user_id, goal=goal)
                s.add(obj)
            else:
                obj.tenant_id = tenant_id
            obj.plan = plan
            obj.status = _coerce_status(status)
            if result is not None:
                obj.result = _safe_json(result)
            if error is not None:
                obj.error = error
            if auth_boundary_id and _is_uuid(auth_boundary_id):
                obj.auth_boundary_id = uuid.UUID(auth_boundary_id)
            if status == "completed":
                obj.completed_at = datetime.now(timezone.utc)
            await s.commit()
    except Exception as e:
        logger.warning(f"⚠️ save_session 失败（已忽略，不影响执行）：{type(e).__name__} {e}")


async def log_audit(session_id: str, event_type: str, actor: str, detail, tenant_id: str = "default") -> None:
    """插入一条审计日志。db 不可用时静默跳过。"""
    if not db.db_available or db.async_session is None:
        return
    detail_str = (
        json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else str(detail)
    )
    try:
        async with db.async_session() as s:
            s.add(
                AuditLog(
                    session_id=uuid.UUID(session_id) if _is_uuid(session_id) else uuid.uuid4(),
                    tenant_id=tenant_id,
                    event_type=event_type,
                    actor=actor,
                    detail=detail_str,
                )
            )
            await s.commit()
    except Exception as e:
        logger.warning(f"⚠️ log_audit 失败（已忽略）：{type(e).__name__} {e}")


async def get_session(session_id: str) -> dict | None:
    if not db.db_available or db.async_session is None or not _is_uuid(session_id):
        return None
    try:
        async with db.async_session() as s:
            obj = await s.get(AgentSession, uuid.UUID(session_id))
            return _session_to_dict(obj) if obj else None
    except Exception:
        return None


async def list_sessions(limit: int = 50, tenant_id: str = "default") -> list[dict]:
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = (
                select(AgentSession)
                .where(AgentSession.tenant_id == tenant_id)
                .order_by(AgentSession.created_at.desc())
                .limit(limit)
            )
            rows = (await s.execute(q)).scalars().all()
            return [_session_to_dict(o) for o in rows]
    except Exception:
        return []


async def get_audit_logs(session_id: str | None = None, limit: int = 200, tenant_id: str = "default") -> list[dict]:
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.created_at.desc())
            if session_id and _is_uuid(session_id):
                q = q.where(AuditLog.session_id == uuid.UUID(session_id))
            rows = (await s.execute(q.limit(limit))).scalars().all()
            return [
                {
                    "id": str(o.id),
                    "session_id": str(o.session_id),
                    "event_type": o.event_type,
                    "actor": o.actor,
                    "detail": o.detail,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in rows
            ]
    except Exception:
        return []


async def save_metric_record(
    kind: str,
    agent: str | None,
    summary: str,
    payload: dict | str,
    tenant_id: str = "default",
) -> None:
    """插入一条效果指标记录。db 不可用时静默跳过。"""
    if not db.db_available or db.async_session is None:
        return
    payload_str = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else str(payload)
    try:
        async with db.async_session() as s:
            s.add(
                MetricsRecord(
                    tenant_id=tenant_id,
                    kind=kind,
                    agent=agent,
                    summary=summary[:256],
                    payload=payload_str,
                )
            )
            await s.commit()
    except Exception as e:
        logger.warning(f"⚠️ save_metric_record 失败（已忽略）：{type(e).__name__} {e}")


async def load_recent_metrics(limit: int = 500) -> list[dict]:
    """加载最近的效果指标记录（重启回灌内存用）。db 不可用时返回空。"""
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = (
                select(MetricsRecord)
                .order_by(MetricsRecord.created_at.desc())
                .limit(limit)
            )
            rows = (await s.execute(q)).scalars().all()
            out = []
            for o in rows:
                try:
                    pl = json.loads(o.payload) if o.payload else {}
                except Exception:
                    pl = {}
                out.append({
                    "kind": o.kind,
                    "agent": o.agent,
                    "summary": o.summary,
                    "payload": pl,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                })
            return out
    except Exception as e:
        logger.warning(f"⚠️ load_recent_metrics 失败（已忽略）：{type(e).__name__} {e}")
        return []


async def load_recent_audit(limit: int = 500) -> list[dict]:
    """加载最近的审计日志（重启回灌内存用）。db 不可用时返回空。"""
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = (
                select(AuditLog)
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
            )
            rows = (await s.execute(q)).scalars().all()
            return [
                {
                    "timestamp": o.created_at.isoformat() if o.created_at else None,
                    "session_id": str(o.session_id),
                    "event_type": o.event_type,
                    "actor": o.actor,
                    "detail": o.detail,
                    "tenant_id": o.tenant_id,
                }
                for o in rows
            ]
    except Exception as e:
        logger.warning(f"⚠️ load_recent_audit 失败（已忽略）：{type(e).__name__} {e}")
        return []


async def save_feedback_record(
    tenant_id: str,
    agent: str,
    action_type: str,
    decision: str,
    context: str = "",
    note: str = "",
    source: str = "intervention",
) -> None:
    """插入一条人类反馈经验（偏好/禁忌记忆的持久化）。db 不可用时静默跳过。"""
    if not db.db_available or db.async_session is None:
        return
    try:
        async with db.async_session() as s:
            s.add(
                FeedbackRecord(
                    tenant_id=tenant_id,
                    agent=agent,
                    action_type=action_type,
                    decision=decision,
                    context=context[:4000],
                    note=note[:512],
                    source=source,
                )
            )
            await s.commit()
    except Exception as e:
        logger.warning(f"⚠️ save_feedback_record 失败（已忽略）：{type(e).__name__} {e}")


async def load_recent_feedback(agent: str | None = None, limit: int = 500) -> list[dict]:
    """加载最近的人类反馈经验（重启回灌内存用）。db 不可用时返回空。"""
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = select(FeedbackRecord).order_by(FeedbackRecord.created_at.desc())
            if agent:
                q = q.where(FeedbackRecord.agent == agent)
            q = q.limit(limit)
            rows = (await s.execute(q)).scalars().all()
            return [
                {
                    "id": str(o.id),
                    "tenant_id": o.tenant_id,
                    "agent": o.agent,
                    "action_type": o.action_type,
                    "decision": o.decision,
                    "context": o.context,
                    "note": o.note,
                    "source": o.source,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in rows
            ]
    except Exception as e:
        logger.warning(f"⚠️ load_recent_feedback 失败（已忽略）：{type(e).__name__} {e}")
        return []


def _session_to_dict(o: AgentSession) -> dict:
    result = json.loads(o.result) if o.result else None
    return {
        "session_id": str(o.id),
        "tenant_id": o.tenant_id,
        "user_id": o.user_id,
        "goal": o.goal,
        "status": o.status.value if hasattr(o.status, "value") else o.status,
        "plan": o.plan,
        "result": result,
        "error": o.error,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "completed_at": o.completed_at.isoformat() if o.completed_at else None,
    }


# ---------------------------------------------------------------------------
# P2 自进化：Prompt 版本库 + 知识图谱事实提议 的持久化（韧性降级，db 不可用静默）
# ---------------------------------------------------------------------------

async def save_prompt_version(
    tenant_id: str,
    agent: str,
    version: int,
    content: str,
    parent_version: int | None = None,
    status: str = "proposed",
    proposer: str = "llm",
    note: str = "",
) -> None:
    """插入一条 Prompt 版本记录。db 不可用时静默跳过。"""
    if not db.db_available or db.async_session is None:
        return
    try:
        async with db.async_session() as s:
            s.add(
                PromptVersion(
                    tenant_id=tenant_id,
                    agent=agent,
                    version=version,
                    content=content,
                    parent_version=parent_version,
                    status=status,
                    proposer=proposer,
                    note=note[:2000],
                )
            )
            await s.commit()
    except Exception as e:
        logger.warning(f"⚠️ save_prompt_version 失败（已忽略）：{type(e).__name__} {e}")


async def load_prompt_versions(agent: str | None = None, limit: int = 500) -> list[dict]:
    """加载 Prompt 版本记录（重启回灌内存用）。db 不可用时返回空。"""
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = select(PromptVersion).order_by(PromptVersion.version.desc())
            if agent:
                q = q.where(PromptVersion.agent == agent)
            q = q.limit(limit)
            rows = (await s.execute(q)).scalars().all()
            return [
                {
                    "id": str(o.id),
                    "tenant_id": o.tenant_id,
                    "agent": o.agent,
                    "version": o.version,
                    "content": o.content,
                    "parent_version": o.parent_version,
                    "status": o.status,
                    "proposer": o.proposer,
                    "note": o.note,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                    "applied_at": o.applied_at.isoformat() if o.applied_at else None,
                }
                for o in rows
            ]
    except Exception as e:
        logger.warning(f"⚠️ load_prompt_versions 失败（已忽略）：{type(e).__name__} {e}")
        return []


async def save_kg_fact_proposal(
    tenant_id: str,
    agent: str,
    subject: str,
    predicate: str,
    object_val: str,
    source: str = "",
    confidence: float = 0.8,
    note: str = "",
) -> None:
    """插入一条知识图谱事实提议。db 不可用时静默跳过。"""
    if not db.db_available or db.async_session is None:
        return
    try:
        async with db.async_session() as s:
            s.add(
                KgFactProposal(
                    tenant_id=tenant_id,
                    agent=agent,
                    subject=subject,
                    predicate=predicate,
                    object_val=object_val,
                    source=source[:256],
                    confidence=float(confidence),
                    note=note[:2000],
                )
            )
            await s.commit()
    except Exception as e:
        logger.warning(f"⚠️ save_kg_fact_proposal 失败（已忽略）：{type(e).__name__} {e}")


async def load_kg_fact_proposals(agent: str | None = None, limit: int = 500) -> list[dict]:
    """加载知识图谱事实提议（重启回灌内存用）。db 不可用时返回空。"""
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = select(KgFactProposal).order_by(KgFactProposal.created_at.desc())
            if agent:
                q = q.where(KgFactProposal.agent == agent)
            q = q.limit(limit)
            rows = (await s.execute(q)).scalars().all()
            return [
                {
                    "id": str(o.id),
                    "tenant_id": o.tenant_id,
                    "agent": o.agent,
                    "subject": o.subject,
                    "predicate": o.predicate,
                    "object_val": o.object_val,
                    "source": o.source,
                    "confidence": o.confidence,
                    "status": o.status,
                    "note": o.note,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in rows
            ]
    except Exception as e:
        logger.warning(f"⚠️ load_kg_fact_proposals 失败（已忽略）：{type(e).__name__} {e}")
        return []



# ---------------------------------------------------------------------------
# 多租户数据源配置持久化（P2-2）
# ---------------------------------------------------------------------------

async def save_tenant_data_source(tenant_id: str, kind: str, config: dict, name: str = "", is_active: bool = True) -> str:
    """保存/更新某租户的数据源配置（同 tenant+kind 幂等 upsert）。返回记录 id。"""
    if not db.db_available or db.async_session is None:
        return ""
    try:
        async with db.async_session() as s:
            existing = (await s.execute(
                select(TenantDataSource).where(
                    TenantDataSource.tenant_id == tenant_id, TenantDataSource.kind == kind
                )
            )).scalars().first()
            cfg_json = json.dumps(config, ensure_ascii=False)
            if existing:
                existing.config_json = cfg_json
                existing.is_active = is_active
                if name:
                    existing.name = name
                rid = existing.id
            else:
                obj = TenantDataSource(
                    tenant_id=tenant_id, kind=kind, name=name,
                    config_json=cfg_json, is_active=is_active,
                )
                s.add(obj)
                await s.flush()
                rid = obj.id
            await s.commit()
            return str(rid)
    except Exception as e:
        logger.warning(f"⚠️ save_tenant_data_source 失败（已忽略）：{type(e).__name__} {e}")
        return ""


async def load_tenant_data_sources(tenant_id: str | None = None) -> list[dict]:
    """加载租户数据源配置（重启回灌 registry 用）。db 不可用时返回空。"""
    if not db.db_available or db.async_session is None:
        return []
    try:
        async with db.async_session() as s:
            q = select(TenantDataSource).where(TenantDataSource.is_active == True)  # noqa: E712
            if tenant_id:
                q = q.where(TenantDataSource.tenant_id == tenant_id)
            rows = (await s.execute(q)).scalars().all()
            return [
                {
                    "id": str(o.id),
                    "tenant_id": o.tenant_id,
                    "kind": o.kind,
                    "name": o.name,
                    "config": json.loads(o.config_json or "{}"),
                    "is_active": o.is_active,
                }
                for o in rows
            ]
    except Exception as e:
        logger.warning(f"⚠️ load_tenant_data_sources 失败（已忽略）：{type(e).__name__} {e}")
        return []


async def delete_tenant_data_source(tenant_id: str, kind: str) -> bool:
    """删除某租户的数据源配置（同时移出 registry）。返回是否成功。"""
    registry_unregistered = False
    try:
        from src.runtime.data_sources.registry import registry
        registry.unregister(kind, tenant_id)
        registry_unregistered = True
    except Exception:
        pass
    if not db.db_available or db.async_session is None:
        return registry_unregistered
    try:
        async with db.async_session() as s:
            row = (await s.execute(
                select(TenantDataSource).where(
                    TenantDataSource.tenant_id == tenant_id, TenantDataSource.kind == kind
                )
            )).scalars().first()
            if row:
                await s.delete(row)
                await s.commit()
                return True
    except Exception as e:
        logger.warning(f"⚠️ delete_tenant_data_source 失败（已忽略）：{type(e).__name__} {e}")
    return registry_unregistered
