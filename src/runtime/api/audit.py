"""审计日志API——优先读库（落库数据），不可用时回退内存"""

from fastapi import APIRouter, Query

from src.meta_agent.audit import audit_logger
from src.runtime.persistence import get_audit_logs

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_logs(session_id: str | None = Query(None), limit: int = Query(50, le=200)):
    """查询审计日志（db 优先，回退内存）"""
    db_logs = await get_audit_logs(session_id=session_id, limit=limit)
    if db_logs:
        return {"source": "db", "logs": db_logs, "total": len(db_logs)}
    logs = audit_logger.get_logs(session_id=session_id, limit=limit)
    return {"source": "memory", "logs": logs, "total": len(logs), "stats": audit_logger.get_stats()}
