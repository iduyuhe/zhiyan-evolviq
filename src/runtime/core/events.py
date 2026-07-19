"""事件系统——Agent执行事件的实时通知

提供事件存储和查询，供前端展示通知列表。
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Event:
    def __init__(self, event_type: str, title: str, message: str, level: str = "info", source: str = "agent"):
        self.id = f"evt-{datetime.now(timezone.utc).timestamp():.0f}-{hash(title) % 10000:04d}"
        self.event_type = event_type
        self.title = title
        self.message = message
        self.level = level  # info / warning / critical / success
        self.source = source
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.read = False


class EventBus:
    """内存事件总线"""

    def __init__(self, max_events: int = 100):
        self._events: list[Event] = []
        self._max_events = max_events

    def publish(self, event_type: str, title: str, message: str, level: str = "info", source: str = "agent") -> Event:
        """发布事件"""
        event = Event(event_type, title, message, level, source)
        self._events.append(event)
        # 保持最大数量
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]
        logger.info(f"[EVENT] [{level.upper()}] {title}")
        return event

    def list(self, limit: int = 20, unread_only: bool = False) -> list[dict]:
        """查询事件列表"""
        events = [e for e in self._events if not e.read] if unread_only else self._events
        events = events[-limit:]
        return [
            {
                "id": e.id,
                "type": e.event_type,
                "title": e.title,
                "message": e.message,
                "level": e.level,
                "source": e.source,
                "timestamp": e.timestamp,
                "read": e.read,
            }
            for e in reversed(events)
        ]

    def mark_read(self, event_id: str) -> bool:
        """标记已读"""
        for e in self._events:
            if e.id == event_id:
                e.read = True
                return True
        return False

    def mark_all_read(self):
        for e in self._events:
            e.read = True

    def unread_count(self) -> int:
        return sum(1 for e in self._events if not e.read)


# 全局单例
event_bus = EventBus()
