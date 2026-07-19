"""效果指标收集器——支撑「效果报告」

记录每个会话的自主执行/人工介入情况，聚合出平台级指标：
- 自主执行率（目标 > 70%）
- 节省工时（Agent自主完成的动作等效人工作业时间）
- 异常准确率（介入事项中人类最终批准的比例）

对应策划方案 模块四「效果报告」(MVP必修)
"""

from __future__ import annotations

from datetime import datetime, timezone

TIME_SAVED_PER_AUTO_ACTION_MIN = 12.0  # 每次自主执行等效节省的人工分钟数（估算）


class MetricsStore:
    """内存指标存储"""

    def __init__(self):
        self._records: list[dict] = []

    def record(self, session_id: str, agent: str, total: int, auto: int, human: int):
        self._records.append({
            "session_id": session_id,
            "agent": agent,
            "total_actions": total,
            "auto_actions": auto,
            "human_actions": human,
            "time_saved_min": auto * TIME_SAVED_PER_AUTO_ACTION_MIN,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_decision(self, intervention_id: str, approved: bool):
        """记录一次人类介入决策，用于计算异常准确率"""
        self._records.append({
            "intervention_id": intervention_id,
            "approved": approved,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": "decision",
        })

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


# 全局单例
metrics = MetricsStore()
