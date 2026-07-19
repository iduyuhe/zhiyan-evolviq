"""异常介入队列——AI原生的人机协同闭环

当Agent的动作超出授权边界时，动作不会被执行，而是进入"待确认"队列。
人类在「异常介入中心」一键审批/驳回。这是平台从"报警器"升级为
"数字员工"的关键契约机制。

对应策划方案 模块四「异常介入中心」(MVP必修)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.runtime.models.authorization import PlannedAction

logger = logging.getLogger(__name__)


class Intervention:
    """一条待人类决策的介入事项"""

    def __init__(
        self,
        session_id: str,
        agent: str,
        action: PlannedAction,
        reason: str,
        boundary_id: str,
    ):
        self.id = f"ivt-{uuid.uuid4().hex[:12]}"
        self.session_id = session_id
        self.agent = agent
        self.action = action
        self.reason = reason
        self.boundary_id = boundary_id
        self.status = "pending"  # pending / approved / rejected
        self.decision_note: str = ""
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.decided_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "agent": self.agent,
            "action": self.action.model_dump(),
            "reason": self.reason,
            "boundary_id": self.boundary_id,
            "status": self.status,
            "decision_note": self.decision_note,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
        }


class InterventionQueue:
    """介入事项队列——内存存储"""

    def __init__(self):
        self._items: dict[str, Intervention] = {}

    def push(self, intervention: Intervention) -> Intervention:
        self._items[intervention.id] = intervention
        logger.info(f"介入事项入队: {intervention.id} | {intervention.action.type} | {intervention.reason}")
        return intervention

    def list(self, status: str | None = None, limit: int = 50) -> list[dict]:
        items = [i for i in self._items.values() if (status is None or i.status == status)]
        items = sorted(items, key=lambda x: x.created_at, reverse=True)
        return [i.to_dict() for i in items[:limit]]

    def get(self, intervention_id: str) -> Intervention | None:
        return self._items.get(intervention_id)

    def decide(self, intervention_id: str, approved: bool, note: str = "") -> Intervention | None:
        item = self._items.get(intervention_id)
        if not item:
            return None
        item.status = "approved" if approved else "rejected"
        item.decision_note = note
        item.decided_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"介入事项决策: {intervention_id} -> {item.status}")
        return item

    def pending_count(self) -> int:
        return sum(1 for i in self._items.values() if i.status == "pending")

    def stats(self) -> dict:
        total = len(self._items)
        decided = sum(1 for i in self._items.values() if i.status != "pending")
        approved = sum(1 for i in self._items.values() if i.status == "approved")
        rejected = sum(1 for i in self._items.values() if i.status == "rejected")
        return {
            "total": total,
            "pending": self.pending_count(),
            "approved": approved,
            "rejected": rejected,
            "decision_rate": round(decided / total, 3) if total else 0.0,
        }


# 全局单例
intervention_queue = InterventionQueue()
