"""事件通知API"""

from fastapi import APIRouter, Query

from src.runtime.core.events import event_bus

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_events(limit: int = Query(20, le=100), unread_only: bool = False):
    """查询事件列表"""
    events = event_bus.list(limit=limit, unread_only=unread_only)
    return {
        "events": events,
        "total": len(events),
        "unread": event_bus.unread_count(),
    }


@router.post("/{event_id}/read")
async def mark_read(event_id: str):
    """标记事件已读"""
    ok = event_bus.mark_read(event_id)
    return {"status": "ok" if ok else "not_found"}


@router.post("/read-all")
async def mark_all_read():
    """标记所有已读"""
    event_bus.mark_all_read()
    return {"status": "ok"}
