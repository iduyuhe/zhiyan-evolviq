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
from src.runtime.models.agent_session import AgentSession, AuditLog, SessionStatus

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
