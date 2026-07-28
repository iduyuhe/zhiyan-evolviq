"""S3-2 相关性打分降噪（#317）

信号 × 租户画像关联度打分：高相关优先推给对应 agent，低相关降噪（不打扰）。

输入：
- 环境信号（UNS environment 事件 dict）：payload.category / payload.title / payload.content /
  entities / source / credibility
- 本租户行为画像（behavior_store.profile，S3-1 供血）
- 本租户订阅规则（env_subscription_store.list_for）

输出 relevance：
    {
      "score": float[0,1],        # 关联度
      "target_agents": [agent_id],# 高相关优先推送的 agent（外圈 4 为主，命中实体可含中圈）
      "suppressed": bool,         # 是否降噪（低相关且非官方）
      "reason": str,              # F4 透明标注：打分依据（不伪装“智能”）
      "category": str,
    }

🔴 隐私红线（MASTER §S3）：
- attention 仅来自本租户画像 + 本租户订阅，绝不跨租户；score_signal 不触碰其他租户数据。
- 绝无任何跨租户聚合到个体可识别粒度的逻辑。
"""

from __future__ import annotations

# ---------- category → 目标 agent 映射（外圈 4 为主；命中实体/深度使用可含中圈）----------
CATEGORY_AGENT_MAP: dict[str, list[tuple[str, float]]] = {
    "policy": [("compliance_q", 1.0), ("executive_cockpit", 0.5)],
    "market": [("procurement_manage", 1.0), ("cost_analysis", 0.5)],
    "benchmark": [("executive_cockpit", 1.0), ("eco_change", 0.4)],
    "supply_chain": [("supply_chain", 1.0)],
    "competitor": [("executive_cockpit", 1.0)],
    "customer_voice": [("executive_cockpit", 1.0)],
}

# 源名 → 类目（租户订阅启用的源，隐含其关注该类目）
# 注意：env_manager 注册源名无 _source 后缀（policy / market / benchmark）
SOURCE_NAME_CATEGORY = {
    "policy": "policy",
    "market": "market",
    "benchmark": "benchmark",
}

# ---------- 打分权重（常量化，便于治理与阈值调参）----------
SUPPRESS_THRESHOLD = 0.25   # 低于此分且非官方 → 降噪（不主动推）
OFFICIAL_FLOOR = 0.40       # 官方信号保底分（不被轻易降噪）
ENTITY_HIT_BONUS = 0.35     # 信号实体命中租户关注实体 → 加分
SUBSCRIPTION_BONUS = 0.50   # 租户订阅了该类目源 → 关注权重
PROFILE_EVENT_BONUS = 0.30  # 行为画像显示关注该类目 → 关注权重
NEUTRAL_BASELINE = 0.50     # 无画像/无关注时中性呈现分（不全降噪）


def derive_attention(profile: dict | None, subscriptions: list[dict] | None) -> dict:
    """从本租户行为画像 + 订阅规则派生「关注类目权重」与「关注实体集」。

    返回 {"category_weights": {cat: float}, "entities": set[str]}。
    任一输入为 None 时退化为空（调用方据此走中性基线）。
    """
    cat_weights: dict[str, float] = {}
    entities: set[str] = set()

    # 1) 订阅启用的源 → 类目关注
    for sub in subscriptions or []:
        if not sub.get("enabled"):
            continue
        cat = SOURCE_NAME_CATEGORY.get(sub.get("source_name", ""))
        if cat:
            cat_weights[cat] = cat_weights.get(cat, 0.0) + SUBSCRIPTION_BONUS

    # 2) 行为画像：top_objects（形如 "kind:id"）+ event_types 中带类目后缀的关注
    if profile:
        for obj in profile.get("top_objects", []) or []:
            oid = obj.get("object") if isinstance(obj, dict) else str(obj)
            if oid and ":" in oid:
                entities.add(oid.split(":", 1)[1])  # 取 id 部分（去 kind 前缀）
        for et, _cnt in (profile.get("event_types", {}) or {}).items():
            if "_" in et:
                tail = et.rsplit("_", 1)[-1]
                if tail in CATEGORY_AGENT_MAP:
                    cat_weights[tail] = cat_weights.get(tail, 0.0) + PROFILE_EVENT_BONUS

    return {"category_weights": cat_weights, "entities": entities}


def _entity_ids(signal: dict) -> set[str]:
    return {str(e).split(":", 1)[-1] for e in (signal.get("entities", []) or [])}


def _text_of(signal: dict) -> str:
    payload = signal.get("payload", {}) or {}
    return " ".join(
        str(payload.get(k, "")) for k in ("title", "content", "summary", "name")
    )


def score_signal(signal: dict, attention: dict) -> dict:
    """对单条环境信号打分，返回 relevance dict。

    纯函数，无副作用、不触碰其他租户数据——易测、隐私安全。
    """
    payload = signal.get("payload", {}) or {}
    category = payload.get("category", "unknown")
    credibility = signal.get("credibility") or "general"
    cat_weights = attention.get("category_weights", {}) or {}
    attention_entities = attention.get("entities", set()) or set()

    score = 0.0
    reasons: list[str] = []

    # 1) 类目关注权重
    cat_w = cat_weights.get(category, 0.0)
    if cat_w > 0:
        score += cat_w
        reasons.append(f"命中你关注的类目「{category}」")
    else:
        reasons.append(f"类目「{category}」非你当前关注重点")

    # 2) 实体命中（强信号：信号涉及你关注的具体对象）
    hit = _entity_ids(signal) & attention_entities
    if hit:
        score += ENTITY_HIT_BONUS
        reasons.append(f"涉及你关注的实体：{', '.join(sorted(hit))}")

    # 3) 中性基线（无画像/无关注时不全降噪，默认可见——避免新租户空流）
    if not cat_weights and not attention_entities:
        score = max(score, NEUTRAL_BASELINE)
        reasons.append("暂无足够画像，按中性呈现")

    # 4) 归一化到 [0,1]
    score = min(1.0, score)

    # 5) 官方保底（F4 可信治理：官方信号不该被相关性降噪淹没）
    if credibility == "official":
        if score < OFFICIAL_FLOOR:
            reasons.append("官方信号保底（credibility=official）")
        score = max(score, OFFICIAL_FLOOR)

    # 6) 目标 agent（外圈 4 为主，按映射权重降序）
    target_agents = [
        a for a, w in sorted(CATEGORY_AGENT_MAP.get(category, []), key=lambda x: -x[1]) if w > 0
    ]

    # 7) 降噪判定（低相关且非官方）
    suppressed = (score < SUPPRESS_THRESHOLD) and (credibility != "official")

    reason = "；".join(reasons) + f"（credibility={credibility}）"
    return {
        "score": round(score, 3),
        "target_agents": target_agents,
        "suppressed": suppressed,
        "reason": reason,
        "category": category,
    }


def rank_intelligence_signals(
    signals: list[dict], attention: dict, include_suppressed: bool = False
) -> tuple[list[dict], int]:
    """给真实情报流逐条打分、降噪过滤、按相关性降序排序。

    返回 (ranked_signals_with_relevance, suppressed_count)。
    ranked 中每条追加 {"kind": "intelligence", "relevance": {...}}。
    """
    ranked: list[dict] = []
    suppressed_count = 0
    for s in signals:
        rel = score_signal(s, attention)
        if rel["suppressed"] and not include_suppressed:
            suppressed_count += 1
            continue
        ranked.append({**s, "kind": "intelligence", "relevance": rel})
    ranked.sort(key=lambda x: x["relevance"]["score"], reverse=True)
    return ranked, suppressed_count
