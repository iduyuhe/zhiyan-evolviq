"""元Agent——审计日志系统

记录所有Agent操作，保障工业场景的可追溯性。
每条审计日志不可篡改（MVP阶段用DB记录，V1引入区块链校验）。
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """审计日志记录器

    内存保留（兼容既有查询）+ 可选异步 sink（落库）。sink 通过 attach_sink 在
    应用启动时挂载；落库以 fire-and-forget 方式派发到运行中的事件循环，绝不阻塞
    调用方，也不因落库失败影响主流程。
    """

    def __init__(self):
        self._logs: list[dict] = []
        self._async_sink: Optional[Callable[[str, str, str, object], Awaitable[None]]] = None

    def attach_sink(self, coro_fn: Callable[[str, str, str, object], Awaitable[None]]) -> None:
        """挂载一个 async 持久化函数：log(session_id, event_type, actor, detail) -> None"""
        self._async_sink = coro_fn

    def log(
        self,
        session_id: str,
        event_type: str,
        actor: str,
        detail: str | dict,
    ):
        """
        记录一条审计日志

        Args:
            session_id: 执行会话ID
            event_type: 事件类型（goal_set/plan_created/approved/executed/rejected/intervened）
            actor: 执行者（human / agent_name）
            detail: 事件详情（文本或JSON）
        """
        detail_str = json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "event_type": event_type,
            "actor": actor,
            "detail": detail_str,
        }
        self._logs.append(entry)
        logger.info(f"[AUDIT] {entry['actor']} | {entry['event_type']} | session={session_id[:8]}...")

        # 异步落库（fire-and-forget，不阻塞、不抛异常）
        if self._async_sink is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_sink(session_id, event_type, actor, detail))
            except RuntimeError:
                # 无运行中的事件循环（纯同步上下文）——跳过持久化
                pass
        return entry

    def get_logs(self, session_id: str | None = None, limit: int = 50) -> list[dict]:
        """查询审计日志"""
        logs = self._logs
        if session_id:
            logs = [l for l in logs if l["session_id"] == session_id]
        return logs[-limit:]

    def get_stats(self) -> dict:
        """审计统计"""
        total = len(self._logs)
        event_types = {}
        for l in self._logs:
            event_types[l["event_type"]] = event_types.get(l["event_type"], 0) + 1
        return {
            "total_logs": total,
            "by_event_type": event_types,
        }


# 单例
audit_logger = AuditLogger()
