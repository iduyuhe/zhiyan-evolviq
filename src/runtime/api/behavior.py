"""S3-1 行为埋点 API（#315）

- POST /behavior/event：前端埋点上报（信号查看等），租户取自 JWT，fail-closed。
- GET  /behavior/events：本租户事件流（管理员调试/后续推荐层消费）。
- GET  /behavior/profile：本租户行为画像（S3-2 打分 / S3-5 导航器的输入）。

🔴 红线：
- 全部端点强租户隔离（租户一律取 JWT，绝不信 body 里的 tenant 字段）。
- 画像仅本租户可见；超级管理员也只能看自己当前租户上下文的画像，
  不提供跨租户个体粒度聚合端点。
- 埋点上报永不 5xx 阻断前端（store.record 内部吞异常）。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.runtime.authn.deps import require_auth
from src.runtime.behavior_store import behavior_store

router = APIRouter(prefix="/behavior", tags=["behavior"])


class BehaviorEventRequest(BaseModel):
    event_type: str  # signal_view / signal_pull / insight_view / ...（开放扩展）
    object_kind: str | None = None
    object_id: str | None = None
    meta: dict | None = None


@router.post("/event")
async def report_event(req: BehaviorEventRequest, u: dict = Depends(require_auth)):
    """前端埋点上报。租户/用户取自 JWT；record 永不抛异常。"""
    if not req.event_type or not req.event_type.strip():
        raise HTTPException(status_code=400, detail="event_type 不能为空")
    rec = await behavior_store.record(
        tenant_id=u["tenant_id"],
        user_id=u.get("username"),
        event_type=req.event_type,
        object_kind=req.object_kind,
        object_id=req.object_id,
        meta=req.meta,
    )
    return {"status": "recorded" if rec else "ignored", "event": rec}


@router.get("/events")
async def list_events(
    event_type: str | None = None,
    limit: int = 100,
    u: dict = Depends(require_auth),
):
    """本租户事件流（时间倒序）。仅管理员可看（含 user_id 明细）。"""
    role = u.get("role", "VIEWER")
    if role not in ("TENANT_ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="仅租户管理员/超级管理员可查看行为事件流")
    items = behavior_store.events_for(u["tenant_id"], event_type=event_type, limit=limit)
    return {"tenant_id": u["tenant_id"], "total": len(items), "events": items}


@router.get("/profile")
async def tenant_profile(days: int = 30, u: dict = Depends(require_auth)):
    """本租户行为画像（聚合，不含个体明细）。所有已登录角色可见。"""
    return behavior_store.profile(u["tenant_id"], days=days)
