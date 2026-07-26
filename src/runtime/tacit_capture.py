"""v21.5 隐性捕获 —— UNS 人/社交/会议/协作四路 → 经验库捕获 + 知识图谱锚定（抽取即锚定）

连接主义（UNS 隐性信号）抽取结构化事实候选 → 符号主义（知识图谱）锚定（draft 待审批门）。
对应战略「三主义活循环」：隐性信号（连接）经抽取锚定为符号事实，待人审门批准入图谱。

韧性降级：抽取 / 锚定任一环失败静默降级，绝不阻断 UNS 与上游（网关、外部系统照常工作）。
无 lifespan 依赖：import 即注册订阅者，测试（httpx ASGITransport 不触发 lifespan）与生产一致。
"""

from __future__ import annotations

import logging

from src.runtime.uns import (
    uns,
    CHANNEL_HUMAN,
    CHANNEL_SOCIAL,
    CHANNEL_MEETING,
    CHANNEL_COLLAB,
)

logger = logging.getLogger(__name__)

# type → 符号主义谓词（抽取即锚定的关系命名，与战略 §3.3 事件 schema 对齐）
TYPE_PREDICATE = {
    "tacit_judgment": "tacit_judges",
    "business_event": "observed_in",
    "decision_rationale": "decided",
    "collab_message": "collaborated_on",
}

TACIT_CHANNELS = (CHANNEL_HUMAN, CHANNEL_SOCIAL, CHANNEL_MEETING, CHANNEL_COLLAB)


def extract_tacit_fact(ev) -> dict:
    """确定性启发式抽取：把隐性信号转成 (subject, predicate, object_val) 候选事实。

    不依赖 LLM（确定性 + 可测 + 韧性）；未来若接 LLM 抽取，可在此切换并回退到本启发式。
    """
    entities = ev.entities or []
    subject = entities[0] if entities else ev.source
    predicate = TYPE_PREDICATE.get(ev.type, "signals")
    object_val = _extract_object(ev)
    return {
        "subject": str(subject),
        "predicate": predicate,
        "object_val": object_val,
        "note": f"{ev.channel}/{ev.type}",
    }


def _extract_object(ev) -> str:
    """从 payload / entities 抽取客体值（确定性回退链）。"""
    p = ev.payload or {}
    for k in ("content", "text", "summary", "judgment", "reason", "value", "name"):
        if k in p and p[k] not in (None, ""):
            return str(p[k])[:300]
    if len(ev.entities or []) > 1:
        return str(ev.entities[1])
    if p:
        return "; ".join(f"{k}={v}" for k, v in list(p.items())[:3])[:300]
    return "<tacit signal>"


def _on_tacit_event(ev) -> None:
    """UNS 四路订阅回调：抽取 → 锚定（KG draft）+ 经验库捕获。"""
    try:
        from src.runtime.experience import experience
        from src.runtime.evolution.kg_facts import kg_facts

        fact = extract_tacit_fact(ev)
        # 符号主义锚定：提议写入知识图谱（draft，待人类审批门）
        try:
            kg_facts.propose(
                tenant_id="default",
                agent=f"tacit:{ev.channel}",
                subject=fact["subject"],
                predicate=fact["predicate"],
                object_val=fact["object_val"],
                source=f"uns:{ev.channel}:{ev.source}",
                confidence=ev.confidence,
                note=fact.get("note", ""),
            )
        except Exception as e:
            logger.warning(f"⚠️ 隐性捕获锚定 KG 失败（不破管）：{e}")
        # 经验库捕获（连接主义隐性信号沉淀为工作记忆）
        try:
            experience.capture_tacit(
                tenant="default",
                channel=ev.channel,
                source=ev.source,
                payload=ev.payload,
                entities=ev.entities,
                extracted=fact,
                confidence=ev.confidence,
            )
        except Exception as e:
            logger.warning(f"⚠️ 隐性捕获落经验库失败（不破管）：{e}")
    except Exception as e:
        logger.warning(f"⚠️ 隐性捕获管道异常（不破管）：{e}")


_HOOKS_REGISTERED = False


def init_tacit_capture() -> None:
    """幂等注册 UNS 四路订阅者（import 即调用一次）。"""
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return
    for ch in TACIT_CHANNELS:
        uns.subscribe(ch, _on_tacit_event)
    _HOOKS_REGISTERED = True


# import 即注册（无 lifespan 依赖，测试/生产一致）
init_tacit_capture()
