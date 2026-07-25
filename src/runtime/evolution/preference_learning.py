"""P2-5 在线偏好学习 lite——基于滚动批准率产出校准信号。

读取经验库的偏好/禁忌记忆，计算该 Agent 的滚动批准率与动作级驳回分布，
产出"信任度校准信号"。该信号**只供参考/驱动其它模块**（如触发 Prompt 复盘、
辅助策略自学习闭环放宽阈值），绝不直接改写任何业务数字（事实锚点）。
"""

from __future__ import annotations

import logging
from collections import Counter

from src.runtime.experience import experience

logger = logging.getLogger(__name__)


def preference_calibration(agent: str) -> dict:
    """返回该 Agent 的在线偏好校准信号。"""
    s = experience.agent_feedback_summary(agent)
    approvals, rejections, recent = s["approvals"], s["rejections"], s["recent_rejections"]
    total = approvals + rejections
    approval_rate = round(approvals / total, 3) if total else None

    # 动作级分布：找出被驳回最多的动作类型
    forbidden = experience.get_forbidden(agent, limit=200)
    by_action = Counter(r.get("action_type") or "未知" for r in forbidden)
    top_action = by_action.most_common(1)[0] if by_action else None

    signals: list[str] = []
    if approval_rate is None:
        verdict = "no_data"
    elif approval_rate >= 0.90 and total >= 5:
        verdict = "trusted"
        signals.append("该 Agent 被高度信任，可结合「规则自学习闭环」适度放宽置信阈值。")
    elif approval_rate < 0.60 or recent >= 3:
        verdict = "needs_review"
        signals.append("该 Agent 近期被频繁纠正，建议收紧授权边界并触发 Prompt 复盘（自进化）。")
    else:
        verdict = "balanced"
        signals.append("该 Agent 信任度处于稳健区间，维持现状。")

    if top_action:
        signals.append(f"重点改进动作：{top_action[0]}（累计被驳回 {top_action[1]} 次）。")

    return {
        "agent": agent,
        "approvals": approvals,
        "rejections": rejections,
        "recent_rejections_24h": recent,
        "approval_rate": approval_rate,
        "sample_size": total,
        "verdict": verdict,
        "signals": signals,
        "top_rejected_action": (top_action[0] if top_action else None),
    }
