"""异常介入中心API——人机协同闭环接口

人类在「异常介入中心」查看Agent因越界而暂停的动作，并一键审批/驳回。
审批后动作状态更新，并记入效果指标。

对应策划方案 模块四「异常介入中心」(MVP必修)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.runtime.core.intervention import intervention_queue
from src.runtime.core.metrics import metrics
from src.meta_agent.audit import audit_logger

router = APIRouter(prefix="/interventions", tags=["interventions"])


class DecisionRequest(BaseModel):
    approved: bool
    note: str = ""


@router.get("")
async def list_interventions(status: str | None = None, limit: int = 50):
    """列出介入事项（可按状态过滤）"""
    items = intervention_queue.list(status=status, limit=limit)
    return {
        "interventions": items,
        "total": len(items),
        "pending": intervention_queue.pending_count(),
        "stats": intervention_queue.stats(),
    }


@router.get("/pending")
async def pending_interventions():
    """仅返回待处理事项（前端红点用）"""
    items = intervention_queue.list(status="pending")
    return {"interventions": items, "count": len(items)}


@router.get("/{intervention_id}")
async def get_intervention(intervention_id: str):
    ivt = intervention_queue.get(intervention_id)
    if not ivt:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return ivt.to_dict()


@router.post("/{intervention_id}/decide")
async def decide_intervention(intervention_id: str, req: DecisionRequest):
    """人类审批/驳回一条介入事项"""
    ivt = intervention_queue.decide(intervention_id, req.approved, req.note)
    if not ivt:
        raise HTTPException(status_code=404, detail="Intervention not found")

    # 记录决策 + 效果指标
    metrics.record_decision(intervention_id, req.approved)
    audit_logger.log(
        ivt.session_id,
        "intervention_decided",
        "human",
        {"intervention_id": intervention_id, "approved": req.approved, "note": req.note},
    )
    return {
        "id": intervention_id,
        "status": ivt.status,
        "approved": req.approved,
        "action": ivt.action.model_dump(),
    }
