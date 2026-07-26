"""v23.0 薄/厚 holon 治理面板 API

聚合授权边界 + 经验统计 + 蓝弧统计 + 策略调参，为每个 Agent 提供自治度概览和调整能力。
"""

from typing import Optional

from fastapi import APIRouter

from src.runtime.experience import experience

router = APIRouter(prefix="/governance", tags=["governance"])


def _autonomy_level(summary: dict, boundary=None) -> str:
    """基于经验反馈统计与授权边界判定 Agent 自治度等级（薄/中/厚）。

    薄 holon: 近期被高频驳回(≥3 次/24h) → 应收紧
    中 holon: 正常状态 → 维持
    厚 holon: 高频采纳 → 可适度放权
    """
    rejections = (summary or {}).get("recent_rejections", 0)
    approvals = (summary or {}).get("approvals", 0)
    total = rejections + approvals

    if total == 0:
        return "medium"  # 无数据，保守中
    if rejections >= 3 and (total > 0 and rejections / total > 0.3):
        return "thin"  # 近期高频驳回 → 薄（收紧）
    if approvals >= 5 and rejections == 0:
        return "thick"  # 全部采纳 → 厚（可放权）
    return "medium"  # 正常


@router.get("/panel")
async def governance_panel():
    """全 Agent 治理面板一览（自治度等级/经验统计/授权边界概览）。"""
    # 获取授权边界列表
    from src.runtime.core.authorization import authorization

    boundaries = authorization.list()
    # 获取策略调参
    try:
        from src.runtime.core.strategy_tuner import tuner
        strategy_signals = tuner.effect_signals()
        strategy_suggestions = tuner.suggest()
    except Exception:
        strategy_signals = {}
        strategy_suggestions = {}

    agents_data = []
    for b in boundaries:
        ag = b.agent if hasattr(b, "agent") else "?"
        summary = experience.agent_feedback_summary(ag) if ag != "?" else {}
        level = _autonomy_level(summary, b)

        # 蓝弧后果统计
        try:
            from src.runtime.consequence import consequence
            all_con = consequence.query(agent=ag, limit=100)
            agent_validated = sum(1 for c in all_con if c.get("match"))
            agent_total = len(all_con)
        except Exception:
            agent_validated = 0
            agent_total = 0

        agents_data.append({
            "agent": ag,
            "autonomy_level": level,
            "boundary": {
                "confidence_threshold": getattr(b, "confidence_threshold", 0.0),
                "auto_execute_actions": len(getattr(b, "auto_execute_actions", [])),
                "require_approval_actions": len(getattr(b, "require_approval_actions", [])),
                "max_daily_autonomous": getattr(b, "max_daily_autonomous", 0),
                "enabled": getattr(b, "enabled", False),
            },
            "experience": {
                "approvals": summary.get("approvals", 0),
                "rejections": summary.get("rejections", 0),
                "recent_rejections": summary.get("recent_rejections", 0),
            },
            "consequence": {
                "total": agent_total,
                "validated": agent_validated,
                "contradicted": agent_total - agent_validated,
            },
        })

    return {
        "summary": {
            "total_agents": len(agents_data),
            "thin": sum(1 for a in agents_data if a["autonomy_level"] == "thin"),
            "medium": sum(1 for a in agents_data if a["autonomy_level"] == "medium"),
            "thick": sum(1 for a in agents_data if a["autonomy_level"] == "thick"),
        },
        "agents": agents_data,
        "strategy_signals": strategy_signals,
        "strategy_suggestions": strategy_suggestions,
    }
