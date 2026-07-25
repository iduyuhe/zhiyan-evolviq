"""P2-1 失败案例采集——从经验库（人类驳回）派生某 Agent 的失败案例。

失败案例是自进化的"养料"：LLM 复盘这些案例后产出候选 prompt 修订。
当前信号源：经验库中被人类「驳回」的反馈（rejected）。未来可扩展执行异常指标。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from src.runtime.experience import experience

logger = logging.getLogger(__name__)

FAILURE_KINDS = {
    "rejection": "人类驳回",
    "low_confidence": "低置信动作",
    "execution_error": "执行异常",
}


@dataclass
class FailureCase:
    id: str
    agent: str
    kind: str            # rejection / low_confidence / execution_error
    action_type: str
    context: str
    note: str
    created_at: str


def collect_failure_cases(agent: str, limit: int = 12) -> list[FailureCase]:
    """从经验库（被人类驳回的反馈）派生该 Agent 的失败案例。异常时安全降级为空。"""
    cases: list[FailureCase] = []
    try:
        for r in experience.get_forbidden(agent, limit=limit):
            cases.append(
                FailureCase(
                    id=str(uuid.uuid4().hex[:12]),
                    agent=agent,
                    kind="rejection",
                    action_type=r.get("action_type", "") or "",
                    context=(r.get("context") or "")[:500],
                    note=(r.get("note") or "")[:200],
                    created_at=r.get("created_at", "") or "",
                )
            )
    except Exception as e:  # 经验库异常不阻断自进化采集
        logger.warning(f"⚠️ 失败案例采集失败（降级为空）：{e}")
    return cases


def failure_summary(cases: list[FailureCase]) -> str:
    """把失败案例格式化为可读文本，喂给 LLM 复盘。"""
    if not cases:
        return "（无失败案例）"
    lines = []
    for i, c in enumerate(cases[:10], 1):
        label = FAILURE_KINDS.get(c.kind, c.kind)
        lines.append(
            f"{i}. [{label}] 动作={c.action_type or 'NA'}\n"
            f"   场景: {c.context or 'NA'}\n"
            f"   批注: {c.note or 'NA'}"
        )
    return "\n".join(lines)
