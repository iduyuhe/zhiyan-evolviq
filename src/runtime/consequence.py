"""v22 蓝弧闭环 —— 执行后果显式回流认知层 + 后果校验

行为主义（执行后果）回流修正符号主义（知识图谱）——三主义活循环的最后"弧"。
当 Agent 执行动作后，后果（执行结果、人类反馈、真实产出）从 UNS gateway/system
通道自动回流，经后果校验：
- 实际匹配预期 → 提升符号置信度（validate）
- 实际不符预期 → 降低置信度 → 触发纠错提议（self-evolution fuel）

与 v20.4 自反思/自进化分工：
- v20.4 做 Prompt 版本化 + RAG 自更新 + 偏好校准（符号层内循环）
- v22 做「行为主义校验」：执行后果回流修正符号（三主义外循环）
- 两者互补：v20.4 决定"怎么学"，v22 提供"学什么学过该纠正"

韧性铁律：任何环失败静默降级，绝不阻塞上游；无 lifespan / 外部依赖。
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, asdict
from threading import Lock
from typing import Any

from src.runtime.uns import uns, CHANNEL_GATEWAY, CHANNEL_SYSTEM

logger = logging.getLogger(__name__)


@dataclass
class ConsequenceRecord:
    """一条执行后果记录。"""
    id: str
    action_id: str
    agent: str
    predicted: dict
    actual: dict
    match: bool
    match_detail: dict
    source: str
    linked_fact_id: str | None
    created_at: float


class ConsequenceTracker:
    """执行后果追踪器——记录后果、校验匹配、回流认知层（蓝弧）。"""

    def __init__(self, maxlen: int = 2000):
        self._records: list[ConsequenceRecord] = []
        self._maxlen = maxlen
        # 待定后果：action_id → {agent, predicted, linked_fact_id, ts}
        self._pending: dict[str, dict] = {}
        self._lock = Lock()

    # ---------------- 外部注入：预期注册 ----------------

    def expect_outcome(
        self,
        action_id: str,
        agent: str,
        predicted: dict,
        linked_fact_id: str | None = None,
    ) -> None:
        """注册一个待校验的预期后果（Agent 执行动作前调用）。"""
        with self._lock:
            self._pending[action_id] = {
                "agent": agent,
                "predicted": dict(predicted),
                "linked_fact_id": linked_fact_id,
                "ts": time.time(),
            }

    # ---------------- 后果记录（核心入口） ----------------

    def record(
        self,
        action_id: str,
        actual: dict,
        source: str = "uns:gateway",
    ) -> ConsequenceRecord | None:
        """记录一条执行后果——校验 → 回流认知层（蓝弧闭合作业）。"""
        pending = self._pending.pop(action_id, None)
        if pending is None:
            # 有后果但无预期注册：记录（轨迹完整性），不做校验
            rec = ConsequenceRecord(
                id=f"cr-{uuid.uuid4().hex[:12]}",
                action_id=action_id,
                agent="unknown",
                predicted={},
                actual=dict(actual),
                match=False,
                match_detail={"reason": "no_predicted_registered"},
                source=source,
                linked_fact_id=None,
                created_at=time.time(),
            )
            with self._lock:
                self._records.append(rec)
                self._trim()
            logger.info(f"🔵 后果记录（无预期）action={action_id}")
            return rec

        predicted = pending["predicted"]
        agent = pending["agent"]
        linked_fact_id = pending.get("linked_fact_id")
        match, detail = self._check_match(predicted, actual)

        rec = ConsequenceRecord(
            id=f"cr-{uuid.uuid4().hex[:12]}",
            action_id=action_id,
            agent=agent,
            predicted=predicted,
            actual=dict(actual),
            match=match,
            match_detail=detail,
            source=source,
            linked_fact_id=linked_fact_id,
            created_at=time.time(),
        )
        with self._lock:
            self._records.append(rec)
            self._trim()

        logger.info(f"🔵 后果校验 [{('✓' if match else '✗')}] action={action_id} agent={agent} match={match}")

        # --- 回流认知层（蓝弧闭合：行为主义 → 修正符号主义）---
        self._update_cognitive_layer(rec, linked_fact_id)

        return rec

    def _trim(self) -> None:
        if len(self._records) > self._maxlen:
            self._records = self._records[-self._maxlen:]

    def _check_match(self, predicted: dict, actual: dict) -> tuple[bool, dict]:
        """确定性后果校验：比较预期与实际的关键字段。

        规则：
        - 数值键：容差 5%
        - 字符串键：精确匹配
        - 特殊预期键（_expect_decrease / _expect_increase）：方向性校验
        """
        details: dict[str, Any] = {}
        matched_keys = 0
        total_keys = 0

        for k, expected_val in predicted.items():
            if k.startswith("_"):
                continue  # 元字段（方向性预期在下文单独处理）
            if k not in actual:
                details[k] = {"expected": expected_val, "actual": None, "match": False, "reason": "key_missing"}
                total_keys += 1
                continue
            actual_val = actual[k]
            total_keys += 1

            if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                if expected_val == 0:
                    match_flag = abs(actual_val) < 0.001
                else:
                    match_flag = abs((actual_val - expected_val) / expected_val) <= 0.05
            else:
                match_flag = str(expected_val) == str(actual_val)

            details[k] = {"expected": expected_val, "actual": actual_val, "match": match_flag}
            if match_flag:
                matched_keys += 1

        # 方向性预期
        for special_key in ("_expect_decrease", "_expect_increase"):
            if special_key in predicted:
                target_key = predicted.get("_target_key", "")
                if target_key and target_key in actual:
                    prev_val = predicted[special_key]
                    curr_val = actual[target_key]
                    if special_key == "_expect_decrease":
                        match_flag = curr_val < prev_val
                    else:
                        match_flag = curr_val > prev_val
                else:
                    match_flag = False
                details[special_key] = {"prev": predicted.get(special_key), "current": actual.get(target_key), "match": match_flag}
                total_keys += 1
                if match_flag:
                    matched_keys += 1

        overall = (matched_keys / max(total_keys, 1)) >= 0.7 if total_keys > 0 else False
        return overall, {"matched_keys": matched_keys, "total_keys": total_keys, "details": details}

    def _update_cognitive_layer(self, rec: ConsequenceRecord, linked_fact_id: str | None) -> None:
        """回写认知层：经验库 + KG 事实置信度调整（自进化燃料）。"""
        # 1. 经验库记录后果反馈（作为强化信号）
        try:
            from src.runtime.experience import experience

            decision = "validated" if rec.match else "contradicted"
            experience.capture_outcome(
                agent=rec.agent,
                action_id=rec.action_id,
                decision=decision,
                match_detail=rec.match_detail,
                predicted=rec.predicted,
                actual=rec.actual,
            )
        except Exception as e:
            logger.debug(f"⚠️ 后果回流经验库异常（不破管）：{e}")

        # 2. KG 事实置信度调整（如果有关联事实）
        if linked_fact_id:
            try:
                from src.runtime.evolution.kg_facts import kg_facts

                kg_facts.validate_fact(
                    kid=linked_fact_id,
                    ok=rec.match,
                    evidence={
                        "action_id": rec.action_id,
                        "match_detail": rec.match_detail,
                        "actual": rec.actual,
                    },
                )
            except Exception as e:
                logger.debug(f"⚠️ 后果回流 KG 异常（不破管）：{e}")

    # ---------------- 查询 ----------------

    def query(self, agent: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            out = self._records
            if agent:
                out = [r for r in out if r.agent == agent]
            out = sorted(out, key=lambda r: r.created_at, reverse=True)[:limit]
            return [asdict(r) for r in out]

    def get_by_action(self, action_id: str) -> ConsequenceRecord | None:
        with self._lock:
            for r in reversed(self._records):
                if r.action_id == action_id:
                    return r
        return None

    def stats(self) -> dict:
        with self._lock:
            total = len(self._records)
            matched = sum(1 for r in self._records if r.match)
            pending_count = len(self._pending)
        return {
            "total_consequences": total,
            "validated": matched,
            "contradicted": total - matched,
            "pending_outcomes": pending_count,
            "match_rate": round(matched / max(total, 1), 3),
        }

    def virtual_consequence(
        self,
        action_id: str,
        agent: str,
        predicted: dict,
        actual: dict,
        match: bool,
        source: str = "virtual:human_approval",
        linked_fact_id: str | None = None,
    ) -> ConsequenceRecord:
        """注册一条虚拟后果（不依赖 UNS 事件，用于隐性捕获等通道）。
        
        v26.0：当人类审批/驳回一条 tacit 通道的 KG 事实时，自动产生虚拟后果，
        使该事实进入蓝弧闭环。
        """
        rec = ConsequenceRecord(
            id=f"cr-{uuid.uuid4().hex[:12]}",
            action_id=action_id,
            agent=agent,
            predicted=dict(predicted),
            actual=dict(actual),
            match=match,
            match_detail={
                "matched_keys": 1,
                "total_keys": 1,
                "details": {"virtual": {"expected": predicted, "actual": actual, "match": match}},
                "source": source,
            },
            source=source,
            linked_fact_id=linked_fact_id,
            created_at=time.time(),
        )
        with self._lock:
            self._records.append(rec)
            self._trim()
        logger.info(f"🔵 虚拟后果 [{('✓' if match else '✗')}] action={action_id} agent={agent}")

        # 回流认知层（蓝弧闭合）
        self._update_cognitive_layer(rec, linked_fact_id)
        return rec

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._pending.clear()


# 进程级单例
consequence = ConsequenceTracker()


# ---------------- UNS 订阅（自动捕获执行后果）----------------

_HOOKS_REGISTERED = False


def _on_consequence_event(ev) -> None:
    """UNS gateway/system 订阅回调：自动捕获执行后果。

    当一个 UNS 事件 payload 含 action_id 字段，即视为一条执行后果。
    自动校验（如果有关联预期）并回流认知层。
    """
    payload = ev.payload or {}
    action_id = payload.get("action_id", "")
    if not action_id:
        return
    actual = {k: v for k, v in payload.items() if k != "action_id"}
    consequence.record(
        action_id=action_id,
        actual=actual,
        source=f"uns:{ev.channel}:{ev.source}",
    )


def init_consequence() -> None:
    """幂等注册 UNS gateway/system 订阅者（import 即调用一次）。"""
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return
    for ch in (CHANNEL_GATEWAY, CHANNEL_SYSTEM):
        uns.subscribe(ch, _on_consequence_event)
    _HOOKS_REGISTERED = True
    logger.info("🔵 蓝弧闭环：UNS gateway/system 订阅已注册")


# import 即注册（无 lifespan 依赖，测试/生产一致）
init_consequence()
