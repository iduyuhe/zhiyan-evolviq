"""S3-4 采纳/驳回反哺（#318，与蓝弧后果回流同构）

把客户对「源推荐（S3-3）/ 信号相关性（S3-2）」的采纳/驳回行为，回流到推荐模型：
- 采纳（adopt）：强化其类目兴趣 → 该类目源推荐度上调。
- 驳回（reject）：弱化该源/类目 → 推荐度下调（F4 透明标注，仍可撤销，绝不静默消失）。

存储复用 S3-1 通用行为事件池（behavior_store）——租户内隔离、DB 韧性、重启恢复，
本模块是「薄聚合层」：按 (target_kind, target_id) 取最新动作 → 派生打分调整量。
单点真相 = behavior_events，无独立表、无双写漂移。

🔴 隐私红线（MASTER §S3）：仅本租户反馈参与本租户推荐；adjustments_for 严格按 tenant 过滤，绝不跨租户。
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict

from src.runtime.behavior_store import behavior_store

logger = logging.getLogger(__name__)

FB_ADOPT = "adopt"
FB_REJECT = "reject"

ADOPT_BOOST = 0.15        # 采纳一个类目 → 该类目推荐度上调量（封顶 1.0）
REJECT_FLOOR = 0.12       # 驳回的源/类目 → 推荐度压到该下限（仍可撤销，不消失）


def _parse_meta(meta) -> dict:
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    try:
        return json.loads(meta) if isinstance(meta, str) else {}
    except Exception:
        return {}


async def record(
    tenant_id: str,
    target_kind: str,
    target_id: str,
    action: str,
    category: str | None = None,
    meta: dict | None = None,
) -> dict | None:
    """记录一条推荐采纳/驳回事件（租户内隔离；复用 behavior_store 持久化）。

    target_kind：行为对象类型——"source"（推荐的信息源）/ "category"（类目）/ "signal"（情报）。
    target_id：源名 / 类目名 / 信号 id。
    action：adopt（采纳）/ reject（驳回）。
    category：该推荐归属的 env 类目（policy/market/benchmark），用于类目级加成。
    """
    if action not in (FB_ADOPT, FB_REJECT):
        raise ValueError(f"action 须为 {FB_ADOPT}/{FB_REJECT}")
    return await behavior_store.record(
        tenant_id,
        "recommendation_feedback",
        user_id=None,
        object_kind=target_kind,
        object_id=target_id,
        meta={"action": action, "category": category or "", **(meta or {})},
    )


def adjustments_for(tenant_id: str) -> dict:
    """聚合本租户反馈 → 打分调整量（最新动作胜出；🔴 仅本租户）。

    返回 {
      "category_boost": {cat: float},       # 采纳强化（类目→+boost，封顶 1.0）
      "rejected_sources": [str],            # 驳回的具体源（压到 REJECT_FLOOR）
      "rejected_categories": [str],         # 驳回的类目（其下全部源压到下限）
      "count": int,                         # 本租户反馈事件总数（可度量）
    }
    """
    events = behavior_store.events_for(tenant_id, "recommendation_feedback", limit=500)
    latest: dict[tuple[str, str], tuple[str, str, str]] = {}
    for ev in events:
        ok = ev.get("object_kind")
        oid = ev.get("object_id")
        if not ok or not oid:
            continue
        m = _parse_meta(ev.get("meta"))
        action = m.get("action")
        cat = m.get("category") or ""
        ts = ev.get("created_at") or ""
        key = (ok, oid)
        prev = latest.get(key)
        if prev is None or ts >= prev[2]:
            latest[key] = (action, cat, ts)

    category_boost = defaultdict(float)
    rejected_sources: set[str] = set()
    rejected_categories: set[str] = set()
    for (ok, oid), (action, cat, _ts) in latest.items():
        if action == FB_REJECT:
            if ok == "source":
                rejected_sources.add(oid)
            if cat:
                rejected_categories.add(cat)
            # 直接驳回某个类目
            if ok == "category" and oid:
                rejected_categories.add(oid)
        elif action == FB_ADOPT:
            # 采纳 → 该类目加分（源采纳记其类目；类目采纳记该类目）
            target_cat = cat or (oid if ok == "category" else None)
            if target_cat:
                category_boost[target_cat] = min(1.0, category_boost[target_cat] + ADOPT_BOOST)

    return {
        "category_boost": dict(category_boost),
        "rejected_sources": sorted(rejected_sources),
        "rejected_categories": sorted(rejected_categories),
        "count": len(events),
    }
