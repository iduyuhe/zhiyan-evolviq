"""经验库——人类反馈驱动的自学习记忆层（P1 规则自学习闭环）

把人类在「异常介入中心」对 Agent 动作的审批/驳回，沉淀为该 Agent 的
「偏好 / 禁忌」记忆：
- approved  → 偏好（该 Agent 在此类动作上被信任，可适度放权）
- rejected  → 禁忌（该 Agent 在此类动作上被否定，应更谨慎 / 收紧）

设计（呼应「韧性降级」与「事实锚点」铁律）：
- 内存 `_records` 为快读主存；`_async_sink` 异步落 SQLite（fire-and-forget），
  绝不阻塞、绝不外溢；db 不可用时静默降级。
- `hydrate()` 在启动期回灌，使偏好/禁忌记忆跨重启累积。
- 本模块只记录「人类决策」，绝不改写 Agent 的业务数字或动作（事实锚点）。
- 反馈信号被 strategy_tuner 读取，反哺「按效果调参」——这是 P1「规则自学习闭环」的落点。

对应 P1：把人类纠正/采纳转化为可持续累积、可被检索的经验记忆。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

RECENT_WINDOW_HOURS = 24  # 「近期」窗口：用于冷却期/近期驳回统计


class ExperienceStore:
    """人类反馈经验存储——内存快读 + 异步落库（重启回灌）。"""

    def __init__(self):
        self._records: list[dict] = []
        self._async_sink: Optional[Callable[[str, str, str, str, str, str, str], Awaitable[None]]] = None

    def attach_sink(self, coro_fn) -> None:
        self._async_sink = coro_fn

    def _persist(self, tenant, agent, action_type, decision, context, note, source):
        if self._async_sink is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._async_sink(tenant, agent, action_type, decision, context, note, source)
            )
        except RuntimeError:
            pass

    def record_feedback(
        self,
        tenant: str,
        agent: str,
        action_type: str,
        decision: str,  # "approved" / "rejected"
        context: str = "",
        note: str = "",
        source: str = "intervention",
    ) -> dict:
        """记录一条人类反馈经验（偏好/禁忌）。返回记录 dict。"""
        decision = decision if decision in ("approved", "rejected") else ("approved" if decision else "rejected")
        rec = {
            "tenant_id": tenant,
            "agent": agent,
            "action_type": action_type,
            "decision": decision,
            "context": context,
            "note": note,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._records.append(rec)
        self._persist(tenant, agent, action_type, decision, context, note, source)
        logger.info(f"🧠 经验反馈 [{decision}] {agent}.{action_type} | tenant={tenant}")
        return rec

    async def hydrate(self, limit: int = 500) -> int:
        """从库回灌最近反馈经验到内存。返回回灌条数。"""
        from src.runtime.persistence import load_recent_feedback

        rows = await load_recent_feedback(limit=limit)
        self._records = list(reversed(rows))  # 库中最旧在前 → 内存保持时间序
        logger.info(f"🧠 经验反馈回灌 {len(self._records)} 条（跨重启累积）")
        return len(self._records)

    # ---------- 查询：供 strategy_tuner 与未来 P2 使用 ----------

    def agent_feedback_summary(self, agent: str) -> dict:
        """该 Agent 的反馈统计：采纳数 / 驳回数 / 近 24h 驳回数。

        供 strategy_tuner 反哺「按效果调参」——近期被频繁驳回的 Agent
        应优先收紧（比单纯看介入队列更细，能定位到具体动作类型）。
        """
        now = datetime.now(timezone.utc)
        approvals = rejections = recent_rejections = 0
        for r in self._records:
            if r["agent"] != agent:
                continue
            if r["decision"] == "approved":
                approvals += 1
            else:
                rejections += 1
                try:
                    ts = datetime.fromisoformat(r["created_at"])
                    if now - ts <= timedelta(hours=RECENT_WINDOW_HOURS):
                        recent_rejections += 1
                except Exception:
                    pass
        return {
            "agent": agent,
            "approvals": approvals,
            "rejections": rejections,
            "recent_rejections": recent_rejections,
        }

    def get_preferences(self, agent: str, limit: int = 20) -> list[dict]:
        """该 Agent 被人类采纳的偏好记忆（context 摘要）。"""
        out = [r for r in self._records if r["agent"] == agent and r["decision"] == "approved"]
        return list(reversed(out))[-limit:]

    def get_forbidden(self, agent: str, limit: int = 20) -> list[dict]:
        """该 Agent 被人类驳回的禁忌记忆（context 摘要）。"""
        out = [r for r in self._records if r["agent"] == agent and r["decision"] == "rejected"]
        return list(reversed(out))[-limit:]

    def all(self, limit: int = 100) -> list[dict]:
        return list(reversed(self._records))[-limit:]


# 全局单例
experience = ExperienceStore()
