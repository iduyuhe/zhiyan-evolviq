"""隐性信号捕获摄入 API（v21.5 落地入口）——把人/社交/会议/协作四路信号喂进 UNS。

这是「传统 ERP 零覆盖的隐性信号主出口」：生产者（人/社交/会议/协作系统）通过本端点
把信号发布到 UNS，随后由 src.runtime.tacit_capture 订阅管道完成
「抽取即锚定」——结构化事实候选入知识图谱（draft 待审批门）+ 经验库捕获。

端点（受全局鉴权门禁）：
    POST /api/tacit-capture/{channel}    channel ∈ human|social|meeting|collab
         body: { source, type?, payload, entities?, confidence? }
    POST /api/tacit-capture              channel 置于 body（同上 + channel 字段）
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.runtime.uns import (
    uns,
    CHANNEL_HUMAN,
    CHANNEL_SOCIAL,
    CHANNEL_MEETING,
    CHANNEL_COLLAB,
)

router = APIRouter(prefix="/tacit-capture", tags=["tacit-capture"])

VALID = {
    CHANNEL_HUMAN: "tacit_judgment",
    CHANNEL_SOCIAL: "business_event",
    CHANNEL_MEETING: "decision_rationale",
    CHANNEL_COLLAB: "collab_message",
}
_HELPERS = {
    CHANNEL_HUMAN: uns.publish_human,
    CHANNEL_SOCIAL: uns.publish_social,
    CHANNEL_MEETING: uns.publish_meeting,
    CHANNEL_COLLAB: uns.publish_collab,
}


class TacitCaptureRequest(BaseModel):
    source: str = Field(..., description="信号来源，如 wecom://group-x / meeting://2026-q3 / emp:zhang")
    type: str | None = Field(None, description="事件类型，缺省按通道默认（tacit_judgment/business_event/...）")
    payload: dict = Field(default_factory=dict, description="结构化信号字段（content/text/summary/...）")
    entities: list = Field(default_factory=list, description="实体列表，如 [LINE:3, EMP:zhang]")
    confidence: float = Field(1.0, description="信号置信度 0~1")


@router.post("/{channel}")
async def ingest_channel(channel: str, req: TacitCaptureRequest):
    if channel not in VALID:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的隐性信号通道: {channel}（支持 {', '.join(VALID)}）",
        )
    helper = _HELPERS[channel]
    ev = helper(
        source=req.source,
        payload=req.payload,
        entities=req.entities,
        type=req.type or VALID[channel],
        confidence=req.confidence,
    )
    return {"status": "captured", "event_id": ev.id, "channel": channel}
