"""ERP / MES 回写审计桥 API

端点（均受全局鉴权门禁保护）：
    POST /api/writeback          提交一条回写（agent 决策 → 业务系统审计记录）
    GET  /api/writeback/pending  查看 pending 队列
    POST /api/writeback/retry    触发 pending 重试
    GET  /api/writeback/stats    桥状态统计
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.runtime.context import get_current_tenant
from src.runtime.data_sources.writeback import writeback_bridge

router = APIRouter(prefix="/writeback", tags=["writeback"])


class WritebackRequest(BaseModel):
    system: str = Field(..., description="回写目标系统：mes / erp")
    agent: str = Field(..., description="产生该决策的 agent 名")
    decision_type: str = Field(..., description="决策类型，如 supply_risk_approval")
    payload: dict = Field(default_factory=dict, description="决策结论 + 依据")
    tenant_id: str = Field("default", description="【已废弃】租户由鉴权上下文决定，此字段被服务端忽略")
    decision_id: str | None = Field(None, description="可选：决策唯一 ID（幂等用）")


class RetryResponse(BaseModel):
    sent: int
    pending_remaining: int


@router.post("")
async def submit_writeback(req: WritebackRequest):
    # P1 修复：租户取自鉴权上下文（require_auth 已 set_current_tenant），
    # 忽略请求体 tenant_id，杜绝越权写他租户。
    tenant_id = get_current_tenant()
    try:
        result = await writeback_bridge.submit(
            system=req.system,
            agent=req.agent,
            decision_type=req.decision_type,
            payload=req.payload,
            tenant_id=tenant_id,
            decision_id=req.decision_id,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"回写提交失败：{e}")
    return result


@router.get("/pending")
async def list_pending():
    return {"tenant_id": get_current_tenant(), "pending": writeback_bridge.pending(get_current_tenant())}


@router.post("/retry", response_model=RetryResponse)
async def retry_pending():
    sent = await writeback_bridge.retry_pending()
    return RetryResponse(sent=sent, pending_remaining=len(writeback_bridge._pending))


@router.get("/stats")
async def stats():
    return writeback_bridge.stats(get_current_tenant())


@router.get("/demo-records")
async def demo_records():
    """查看演示审计接收端实际收到的记录（验证回写实执行闭环）。按当前租户隔离。"""
    try:
        from src.runtime.data_sources.demo_audit_sink import received
        tenant = get_current_tenant()
        recs = [r for r in received() if r.get("tenant_id") == tenant]
    except Exception:
        recs = []
    return {"tenant_id": tenant, "count": len(recs), "records": recs}
