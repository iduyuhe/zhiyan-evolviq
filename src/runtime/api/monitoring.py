"""监控告警 API（v28.3）

端点（均受全局鉴权门禁保护）：
    GET  /monitoring/alerts   查询告警（可按 kind 过滤）
    GET  /monitoring/status   监控器状态（阈值、告警总数、登录观察窗）
    POST /monitoring/check    手动触发一轮全量检测
"""

from fastapi import APIRouter, Query

from src.runtime.monitoring import alert_monitor

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/alerts")
async def list_alerts(
    kind: str | None = Query(None, description="过滤：writeback_backlog / gateway_stale / login_anomaly"),
    n: int = Query(50, ge=1, le=200),
):
    return {"alerts": alert_monitor.alerts(kind=kind, n=n)}


@router.get("/status")
async def status():
    return alert_monitor.status()


@router.post("/check")
async def run_checks(tenant_id: str = Query("default")):
    fired = alert_monitor.run_checks(tenant_id)
    return {"fired": fired, "count": len(fired)}
