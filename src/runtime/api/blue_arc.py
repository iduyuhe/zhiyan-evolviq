"""蓝弧闭环驱动 API（v22 落地入口）——让「决策→执行→反馈→再学习」可被显式驱动与观测。

consequence.py 已实现闭环核心（预期注册 expect_outcome → 后果校验 record →
回流经验库 + KG 置信度）。本 API 提供显式入口：
    POST /api/blue-arc/act      声明一个动作 + 预期后果 → 返回 action_id（预期注册）
    POST /api/blue-arc/observe   上报该动作的实际后果 → 触发校验与认知层回流
    GET  /api/blue-arc/status    闭环统计（validated / contradicted / pending）
这也与 UNS gateway/system 自动捕获（payload 含 action_id）互补。
"""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.runtime.consequence import consequence

router = APIRouter(prefix="/blue-arc", tags=["blue-arc"])


class ActRequest(BaseModel):
    agent: str = Field(..., description="执行动作的 agent")
    action_type: str = Field("decision", description="动作类型")
    predicted: dict = Field(default_factory=dict, description="预期后果，如 {oee: 0.9} 或 {_expect_decrease: 0.8, _target_key: 'defect'}")
    linked_fact_id: str | None = Field(None, description="可选：关联的 KG 事实 id（校验后调其置信度）")


class ObserveRequest(BaseModel):
    action_id: str = Field(..., description="act 返回的 action_id")
    actual: dict = Field(default_factory=dict, description="实际后果字段")
    source: str = Field("api", description="后果来源")


@router.post("/act")
async def act(req: ActRequest):
    action_id = f"act:{uuid.uuid4().hex[:12]}"
    consequence.expect_outcome(
        action_id=action_id,
        agent=req.agent,
        predicted=req.predicted,
        linked_fact_id=req.linked_fact_id,
    )
    return {"action_id": action_id, "status": "expected", "agent": req.agent}


@router.post("/observe")
async def observe(req: ObserveRequest):
    rec = consequence.record(action_id=req.action_id, actual=req.actual, source=req.source)
    if rec is None or rec.match_detail.get("reason") == "no_predicted_registered":
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="action_id 无预期注册或已结算")
    return {
        "action_id": req.action_id,
        "match": rec.match,
        "validated": rec.match,
        "match_detail": rec.match_detail,
    }


@router.get("/status")
async def status():
    return consequence.stats()
