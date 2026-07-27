"""v30.0 α 环境感知第⑥路 —— credibility 分级门（F4 可信治理落地）

订阅 UNS environment 路，按 credibility 分流：
- official（官方发布）    → 直接走「抽取即锚定」（KG draft + 经验库 + 预期后果），与隐性捕获同构。
- authoritative / general → 一律进 `_needs_review` 审核队列，人工批准后才锚定；驳回即丢弃。

红线（F4 可信治理）：非官方信号绝不直接进入真相源三主义循环；官方为锚，其余必筛。
韧性铁律：任一环失败静默降级，绝不阻断 UNS 与上游源适配器。
无 lifespan 依赖：import 即注册订阅者（httpx ASGITransport 不触发 lifespan，测试/生产一致）。
"""

from __future__ import annotations

import logging
import time
import uuid

from src.runtime.uns import uns, CHANNEL_ENVIRONMENT, CRED_OFFICIAL

logger = logging.getLogger(__name__)

# 审核队列容量上限（内存环形，防无界增长）
_REVIEW_MAXLEN = 1000


class EnvReviewQueue:
    """非官方环境信号审核队列（_needs_review 门）。"""

    def __init__(self):
        self._items: list[dict] = []

    def add(self, ev) -> dict:
        item = {
            "id": str(uuid.uuid4()),
            "event_id": ev.id,
            "channel": ev.channel,
            "source": ev.source,
            "type": ev.type,
            "payload": ev.payload,
            "entities": ev.entities,
            "confidence": ev.confidence,
            "credibility": ev.credibility,
            "status": "pending",
            "ts": time.time(),
        }
        self._items.append(item)
        if len(self._items) > _REVIEW_MAXLEN:
            self._items = self._items[-_REVIEW_MAXLEN:]
        return item

    def list(self, status: str | None = "pending") -> list[dict]:
        if status is None:
            return list(self._items)
        return [i for i in self._items if i["status"] == status]

    def get(self, item_id: str) -> dict | None:
        for i in self._items:
            if i["id"] == item_id:
                return i
        return None

    def approve(self, item_id: str, reviewer: str = "human") -> dict | None:
        """人工批准：非官方信号经审后视同可信 → 走锚定管道。"""
        item = self.get(item_id)
        if item is None or item["status"] != "pending":
            return None
        item["status"] = "approved"
        item["reviewer"] = reviewer
        item["reviewed_ts"] = time.time()
        _anchor(_ItemEvent(item))
        return item

    def reject(self, item_id: str, reviewer: str = "human") -> dict | None:
        item = self.get(item_id)
        if item is None or item["status"] != "pending":
            return None
        item["status"] = "rejected"
        item["reviewer"] = reviewer
        item["reviewed_ts"] = time.time()
        return item

    def counts(self) -> dict:
        c: dict[str, int] = {}
        for i in self._items:
            c[i["status"]] = c.get(i["status"], 0) + 1
        return c

    def clear(self) -> None:
        self._items.clear()


class _ItemEvent:
    """把审核队列条目还原成事件形状，供锚定管道复用。"""

    def __init__(self, item: dict):
        self.id = item["event_id"]
        self.channel = item["channel"]
        self.source = item["source"]
        self.type = item["type"]
        self.payload = item["payload"]
        self.entities = item["entities"]
        self.confidence = item["confidence"]
        self.credibility = item["credibility"]


env_review = EnvReviewQueue()


def _anchor(ev) -> None:
    """抽取即锚定（与隐性捕获同构）：KG draft + 预期后果 + 经验库。"""
    try:
        from src.runtime.tacit_capture import extract_tacit_fact
        from src.runtime.experience import experience
        from src.runtime.evolution.kg_facts import kg_facts

        fact = extract_tacit_fact(ev)
        proposal_id = None
        try:
            prop = kg_facts.propose(
                tenant_id="default",
                agent=f"env:{ev.source}",
                subject=fact["subject"],
                predicate=fact["predicate"],
                object_val=fact["object_val"],
                source=f"uns:environment:{ev.source}",
                confidence=ev.confidence,
                note=f"env/{ev.type}/credibility={getattr(ev, 'credibility', None)}",
            )
            proposal_id = prop.get("id")
        except Exception as e:
            logger.warning(f"⚠️ 环境感知锚定 KG 失败（不破管）：{e}")

        if proposal_id:
            try:
                from src.runtime.consequence import consequence

                consequence.expect_outcome(
                    action_id=f"virtual:env:{proposal_id}",
                    agent="env:perception",
                    predicted={fact["predicate"]: 1.0},
                    linked_fact_id=proposal_id,
                )
            except Exception as e:
                logger.debug(f"⚠️ 环境感知注册预期失败（不破管）：{e}")

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
            logger.warning(f"⚠️ 环境感知落经验库失败（不破管）：{e}")
    except Exception as e:
        logger.warning(f"⚠️ 环境感知锚定管道异常（不破管）：{e}")


def _on_env_event(ev) -> None:
    """UNS environment 路订阅回调：credibility 分级门。"""
    try:
        if getattr(ev, "credibility", None) == CRED_OFFICIAL:
            _anchor(ev)  # 官方为锚：直接锚定
        else:
            env_review.add(ev)  # 非官方必筛：进 _needs_review 审核队列
    except Exception as e:
        logger.warning(f"⚠️ 环境感知分级门异常（不破管）：{e}")


_HOOKS_REGISTERED = False


def init_env_perception() -> None:
    """幂等注册 UNS environment 路订阅者（import 即调用一次）。"""
    global _HOOKS_REGISTERED
    if _HOOKS_REGISTERED:
        return
    uns.subscribe(CHANNEL_ENVIRONMENT, _on_env_event)
    _HOOKS_REGISTERED = True


def reset_env_perception() -> None:
    """测试重置：清空注册标记，下次 init_env_perception 会重新订阅。"""
    global _HOOKS_REGISTERED
    _HOOKS_REGISTERED = False


init_env_perception()
