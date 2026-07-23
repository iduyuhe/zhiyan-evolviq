"""审计日志API——优先读库（落库数据），不可用时回退内存（多租户版）

所有查询按当前租户隔离；未携带密钥 → 默认租户 default。
"""

from fastapi import APIRouter, Query, Depends

from src.meta_agent.audit import audit_logger
from src.runtime.persistence import get_audit_logs
from src.runtime.api.deps import get_tenant

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_logs(
    session_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    tenant: str = Depends(get_tenant),
):
    """查询当前租户的审计日志（db 优先，回退内存）"""
    db_logs = await get_audit_logs(session_id=session_id, limit=limit, tenant_id=tenant)
    if db_logs:
        return {"tenant_id": tenant, "source": "db", "logs": db_logs, "total": len(db_logs)}
    logs = audit_logger.get_logs(session_id=session_id, limit=limit)
    # 内存回退也按租户过滤
    logs = [l for l in logs if l.get("tenant_id", "default") == tenant]
    return {
        "tenant_id": tenant,
        "source": "memory",
        "logs": logs,
        "total": len(logs),
        "stats": audit_logger.get_stats(),
    }
