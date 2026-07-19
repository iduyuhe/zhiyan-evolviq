"""策略调参器——控制台「按效果调参」的核心引擎

把分散在三个地方的信号汇聚成可操作的策略建议：
- 授权边界（authorization）：confidence_threshold / max_daily_autonomous 等实时旋钮
- 效果指标（metrics）：自主率、节省工时、介入准确率（全局 + 按 Agent）
- 介入队列（intervention_queue）：各 Agent 的审批/驳回/待处理分布

输出两类能力：
1. effect_signals()  —— 一页看清每个 Agent 的「放权度 vs 人类信任度」
2. suggest()         —— 基于效果的规则引擎，给出「该放宽/收紧哪个旋钮」的具体建议
3. apply() / apply_suggestion() —— 真正改写运行时授权边界（非死代码），并留审计轨迹

事实锚点铁律：本模块只调整策略阈值（confidence_threshold 等），绝不改写任何业务数字或动作。

对应策划方案 V1-4「控制台策略调整·按效果调参」
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.runtime.core.authorization import authorization
from src.runtime.core.intervention import intervention_queue
from src.runtime.core.metrics import metrics

logger = logging.getLogger(__name__)

TARGET_AUTONOMOUS_RATE = 0.70
CONF_MIN, CONF_MAX = 0.50, 0.95  # 置信阈值安全夹紧区间


class StrategyTuner:
    """单例：策略旋钮的读取 / 建议 / 调整 / 审计"""

    def __init__(self):
        self._history: list[dict] = []
        self._seq = 0
        self._cache: list[dict] = []  # 最近一次 suggest() 产出的建议，供 apply_suggestion 反查

    # ---------- 读取：当前策略旋钮 ----------
    def current(self) -> list[dict]:
        """所有 Agent 的当前策略旋钮（来自授权引擎，运行时实时生效）"""
        return [
            {
                "boundary_id": b.id,
                "agent": b.agent,
                "name": b.name,
                "confidence_threshold": b.confidence_threshold,
                "price_tolerance_pct": b.price_tolerance_pct,
                "max_lock_qty": b.max_lock_qty,
                "max_daily_autonomous": b.max_daily_autonomous,
                "auto_execute_actions": b.auto_execute_actions,
                "require_approval_actions": b.require_approval_actions,
                "enabled": b.enabled,
            }
            for b in authorization.list()
        ]

    # ---------- 读取：效果信号 ----------
    def _agent_intervention_stats(self) -> dict[str, dict]:
        """按 Agent 统计介入队列的 批准/驳回/待处理 分布"""
        stats: dict[str, dict] = {}
        for ivt in intervention_queue.list(limit=10000):
            a = ivt["agent"]
            d = stats.setdefault(a, {"approved": 0, "rejected": 0, "pending": 0})
            d[ivt["status"]] = d.get(ivt["status"], 0) + 1
        return stats

    def effect_signals(self) -> dict:
        """一页看清每个 Agent 的「放权度 vs 人类信任度」"""
        per_agent = {r["agent"]: r for r in metrics.per_agent_report()}
        ivt = self._agent_intervention_stats()
        signals: dict[str, dict] = {}
        for b in authorization.list():
            a = b.agent
            pa = per_agent.get(a, {})
            iv = ivt.get(a, {})
            decided = iv.get("approved", 0) + iv.get("rejected", 0)
            approval_rate = round(iv["approved"] / decided, 3) if decided else None
            signals[a] = {
                "autonomous_rate": pa.get("autonomous_rate", 0.0),
                "total_actions": pa.get("total_actions", 0),
                "auto_actions": pa.get("auto_actions", 0),
                "interventions_approved": iv.get("approved", 0),
                "interventions_rejected": iv.get("rejected", 0),
                "interventions_pending": iv.get("pending", 0),
                "intervention_approval_rate": approval_rate,
                "sample_size": pa.get("total_actions", 0) + decided,
            }
        return signals

    # ---------- 建议：效果驱动的规则引擎 ----------
    def _mk(self, b, param: str, value, direction: str, rationale: str, expected: str) -> dict:
        self._seq += 1
        return {
            "id": f"sug-{self._seq:04d}",
            "agent": b.agent,
            "boundary_id": b.id,
            "param": param,
            "current": getattr(b, param),
            "suggested": value,
            "direction": direction,  # widen / tighten
            "rationale": rationale,
            "expected_effect": expected,
        }

    def suggest(self) -> dict:
        """基于效果信号产出调参建议；无数据时不臆造（sample_size 不足则跳过）。"""
        signals = self.effect_signals()
        suggestions: list[dict] = []
        for b in authorization.list():
            a = b.agent
            s = signals.get(a, {})
            ar = s.get("autonomous_rate", 0.0)
            apr = s.get("intervention_approval_rate")
            rej = s.get("interventions_rejected", 0)
            n = s.get("sample_size", 0)

            # 规则 1：自主率低于目标，且人类高批准率 → Agent 偏保守，建议下调置信阈值放权
            if ar < TARGET_AUTONOMOUS_RATE and apr is not None and apr >= 0.85 and n >= 3:
                new_th = max(CONF_MIN, round(b.confidence_threshold - 0.05, 2))
                if new_th < b.confidence_threshold:
                    suggestions.append(self._mk(
                        b, "confidence_threshold", new_th, "widen",
                        f"自主率 {ar:.0%} 低于目标 {TARGET_AUTONOMOUS_RATE:.0%}，且人工批准率 {apr:.0%} 高→动作偏保守，建议下调置信阈值放权",
                        "预计提升该 Agent 自主执行比例，减少不必要的升级",
                    ))
            # 规则 2：有驳回或低批准率 → Agent 偏激进，建议上调置信阈值收紧
            elif (rej > 0 or (apr is not None and apr < 0.60)) and n >= 3:
                new_th = min(CONF_MAX, round(b.confidence_threshold + 0.05, 2))
                if new_th > b.confidence_threshold:
                    suggestions.append(self._mk(
                        b, "confidence_threshold", new_th, "tighten",
                        f"人工驳回 {rej} 次 / 批准率 {apr if apr is not None else 'NA'} 偏低→动作偏激进，建议上调置信阈值收紧",
                        "预计减少越界动作升级，提升人工处置精准度",
                    ))
            # 规则 3：稳健且高自主 + 高批准 → 上调每日自主上限释放产能
            elif ar >= 0.85 and apr is not None and apr >= 0.90 and n >= 5:
                new_cap = b.max_daily_autonomous + 5
                suggestions.append(self._mk(
                    b, "max_daily_autonomous", new_cap, "widen",
                    f"自主率 {ar:.0%} 且批准率 {apr:.0%} 均优→运行稳健，建议上调每日自主上限",
                    "在不超风险前提下释放更多自主产能",
                ))

        self._cache = suggestions
        return {
            "target_autonomous_rate": TARGET_AUTONOMOUS_RATE,
            "global": metrics.effect_report(),
            "suggestions": suggestions,
        }

    # ---------- 调整：真正改写运行时旋钮 + 审计 ----------
    def apply(self, agent: str, param: str, value, reason: str, basis: str = "manual") -> dict:
        """控制台直接调参：夹紧后写入授权引擎，记入审计轨迹。"""
        b = authorization.get_for_agent(agent)
        if not b:
            raise KeyError(f"未找到 Agent 的授权边界: {agent}")
        if param == "confidence_threshold":
            value = max(CONF_MIN, min(CONF_MAX, float(value)))
        elif param == "max_daily_autonomous":
            value = max(1, int(value))
        elif param == "price_tolerance_pct":
            value = max(0.0, float(value))
        elif param == "max_lock_qty":
            value = max(0, int(value))
        else:
            raise ValueError(f"不支持调整的参数: {param}")

        old = getattr(b, param)
        updated = authorization.patch(b.id, **{param: value})
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "boundary_id": b.id,
            "param": param,
            "old": old,
            "new": value,
            "reason": reason,
            "basis": basis,
        }
        self._history.append(entry)
        logger.info(f"🎚️ 策略调参 [{basis}] {agent}.{param}: {old} → {value} | {reason}")
        return {
            "status": "applied",
            "agent": agent,
            "param": param,
            "old": old,
            "new": value,
            "boundary": updated.model_dump(),
        }

    def apply_suggestion(self, suggestion_id: str, reason: str = "") -> dict:
        """按建议 ID 应用（控制台点「采纳建议」时调用）。"""
        sug = next((s for s in self._cache if s["id"] == suggestion_id), None)
        if not sug:
            raise KeyError(f"建议不存在或已过期: {suggestion_id}")
        return self.apply(
            sug["agent"], sug["param"], sug["suggested"],
            reason or sug["rationale"], basis="suggestion",
        )

    def history(self) -> list[dict]:
        """调参审计轨迹（最新在前）"""
        return list(reversed(self._history))


# 全局单例
tuner = StrategyTuner()
