"""效果指标收集器——支撑「效果报告」

记录每个会话的自主执行/人工介入情况，聚合出平台级指标：
- 自主执行率（目标 > 70%）
- 节省工时（Agent自主完成的动作等效人工作业时间）
- 异常准确率（介入事项中人类最终批准的比例）

对应策划方案 模块四「效果报告」(MVP必修)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from src.runtime.persistence import load_recent_metrics, save_metric_record

logger = logging.getLogger(__name__)

TIME_SAVED_PER_AUTO_ACTION_MIN = 12.0  # 每次自主执行等效节省的人工分钟数（估算）


class MetricsStore:
    """效果指标存储——内存快读 + 异步落库（重启回灌，效果信号不丢）。

    设计（呼应「韧性降级」铁律）：
    - 内存 `_records` 为快读主存，查询零延迟。
    - `_async_sink` 为落库函数（启动时挂载 persistence.save_metric_record），
      fire-and-forget 派发到事件循环，绝不阻塞、绝不外溢。
    - `hydrate()` 在应用启动时从库回灌最近 N 条，使效果信号跨重启累积，
      支撑「按效果调参」基于历史而非每重启清零。
    """

    def __init__(self):
        self._records: list[dict] = []
        self._async_sink: Optional[Callable[[str, str, str, dict, str], Awaitable[None]]] = None

    def attach_sink(self, coro_fn: Callable[[str, str, str, dict, str], Awaitable[None]]) -> None:
        self._async_sink = coro_fn

    def _persist(self, kind: str, agent: Optional[str], summary: str, payload: dict, tenant: str = "default") -> None:
        if self._async_sink is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_sink(kind, agent, summary, payload, tenant))
        except RuntimeError:
            # 无运行中的事件循环——跳过持久化（内存已保留）
            pass

    def record(self, session_id: str, agent: str, total: int, auto: int, human: int, tenant: str = "default"):
        rec = {
            "session_id": session_id,
            "agent": agent,
            "total_actions": total,
            "auto_actions": auto,
            "human_actions": human,
            "time_saved_min": auto * TIME_SAVED_PER_AUTO_ACTION_MIN,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._records.append(rec)
        self._persist("action", agent, f"{agent}: {auto}/{total} 自主", payload=rec, tenant=tenant)

    def record_decision(self, intervention_id: str, approved: bool, tenant: str = "default"):
        """记录一次人类介入决策，用于计算异常准确率"""
        rec = {
            "intervention_id": intervention_id,
            "approved": approved,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": "decision",
        }
        self._records.append(rec)
        self._persist("decision", None, f"介入决策: {'批准' if approved else '驳回'}", payload=rec, tenant=tenant)

    async def hydrate(self, limit: int = 500) -> int:
        """从库回灌最近的效果指标记录到内存。返回回灌条数。"""
        rows = await load_recent_metrics(limit=limit)
        # 反向（库中最旧在前）→ 内存保持时间序；payload 即 record()/record_decision()
        # 写入的原始 dict，保证「内存直写」与「库回灌」两种来源下 effect_report 字段假设一致
        self._records = [r["payload"] for r in reversed(rows) if r.get("payload")]
        logger.info(f"📈 效果指标回灌 {len(self._records)} 条（跨重启累积）")
        return len(self._records)

    def effect_report(self) -> dict:
        sessions = [r for r in self._records if "total_actions" in r]
        decisions = [r for r in self._records if r.get("kind") == "decision"]

        total_actions = sum(r["total_actions"] for r in sessions)
        auto_actions = sum(r["auto_actions"] for r in sessions)
        human_actions = sum(r["human_actions"] for r in sessions)
        time_saved_min = sum(r["time_saved_min"] for r in sessions)

        approved = sum(1 for d in decisions if d["approved"])
        decided = len(decisions)
        accuracy = round(approved / decided, 3) if decided else 0.0

        return {
            "sessions": len(sessions),
            "total_actions": total_actions,
            "auto_actions": auto_actions,
            "human_actions": human_actions,
            "autonomous_rate": round(auto_actions / total_actions, 3) if total_actions else 0.0,
            "time_saved_hours": round(time_saved_min / 60.0, 1),
            "interventions_decided": decided,
            "intervention_accuracy": accuracy,
            "target_autonomous_rate": 0.7,
            "meets_target": (auto_actions / total_actions) >= 0.7 if total_actions else False,
        }

    def per_agent_report(self) -> list[dict]:
        """按 Agent 聚合效果明细，支撑「按效果调参」的精细化建议。"""
        by_agent: dict[str, dict] = {}
        for r in self._records:
            if "total_actions" not in r:
                continue
            a = r["agent"]
            d = by_agent.setdefault(a, {
                "agent": a, "sessions": 0, "total_actions": 0,
                "auto_actions": 0, "human_actions": 0, "time_saved_min": 0.0,
            })
            d["sessions"] += 1
            d["total_actions"] += r["total_actions"]
            d["auto_actions"] += r["auto_actions"]
            d["human_actions"] += r["human_actions"]
            d["time_saved_min"] += r["time_saved_min"]
        out = []
        for d in by_agent.values():
            total = d["total_actions"]
            auto = d["auto_actions"]
            out.append({
                **d,
                "autonomous_rate": round(auto / total, 3) if total else 0.0,
                "time_saved_hours": round(d["time_saved_min"] / 60.0, 1),
            })
        return out

    # ---- 北极星指标：决策实时化率 ----
    def record_decision_realization(self, decision_id: str, realized: bool, real_time: bool, tenant: str = "default"):
        """记录一次「决策实时化」事件（北极星指标原料）。

        realized：该决策是否被系统实时支撑（外部信号 × 内部数据即时触达）
        real_time：是否为真实租户数据（False = DEMO_DATA 演示态，不计入北极星真实率）
        真实率仅统计 real_time=True 的事件；DEMO 数据单独给出演示率，二者不混入。
        """
        rec = {
            "decision_id": decision_id,
            "realized": realized,
            "real_time": real_time,
            "is_demo": not real_time,
            "tenant": tenant,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": "decision_realization",
        }
        self._records.append(rec)
        self._persist("decision_realization", None, f"决策实时化: {'是' if realized else '否'}",
                      payload=rec, tenant=tenant)

    def already_seeded(self, prefix: str) -> bool:
        """幂等判定：是否已注入过某前缀的真实信号（跨重启不重复累计）。"""
        return any(
            r.get("kind") == "decision_realization"
            and str(r.get("decision_id", "")).startswith(prefix)
            for r in self._records
        )

    def north_star_report(self) -> dict:
        """北极星指标报告：决策实时化率。

        仅真实租户数据（real_time=True）计入真实率；demo 演示态（real_time=False）单独给演示率，
        二者严格分离、不混入。P1-4 起：杜特第0号真实客户注入 real_time=True 信号后，
        真实率从 None(0%) 起跳，real_time_active 翻 True。
        """
        events = [r for r in self._records if r.get("kind") == "decision_realization"]
        real = [e for e in events if e.get("real_time")]
        demo = [e for e in events if not e.get("real_time")]
        real_total = len(real)
        real_realized = sum(1 for e in real if e["realized"])
        demo_total = len(demo)
        demo_realized = sum(1 for e in demo if e["realized"])
        return {
            "decision_realization_rate_real": round(real_realized / real_total, 3) if real_total else None,
            "decision_realization_count_real": real_total,
            "decision_realization_rate_demo": round(demo_realized / demo_total, 3) if demo_total else 0.0,
            "decision_realization_count_demo": demo_total,
            "real_time_active": real_total > 0,
            "demo_data_active": demo_total > 0,
            "target_mvp": 0.4,
            "target_steady": 0.85,
            "note": "real 率基于真实租户数据(real_time=True)；demo 率基于演示态(DEMO_DATA)。"
                    "杜特第0号真实客户已注入真实信号，真实率已从 0% 起跳。",
        }


# 全局单例
metrics = MetricsStore()
