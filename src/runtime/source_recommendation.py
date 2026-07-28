"""S3-3 源推荐（#317，γ1）

按租户行业 / 物料（BOM）/ 行为画像 推荐值得订阅的环境信息源。

输入（全部本租户，绝不跨租户）：
- 行为画像（behavior_store.profile，S3-1 供血）：反推常用智能体 → 类目兴趣
- BOM 物料名（bom_store 全量 items）：关键词启发式 → 类目兴趣 + 透明物料证据
- 行业（ZHIYAN_INDUSTRY 环境变量）：给对应 env 类目默认兴趣
- 已知源清单（env_manager.list）+ 本租户订阅规则：产出推荐 + 已订阅确认

输出 recommend_sources：
    [{
      "source_name", "kind", "label", "credibility", "category",
      "score": float[0,1],        # 推荐度
      "subscribed": bool,         # 是否已订阅（已订阅=确认，未订阅=draft 待人审）
      "is_default": bool,         # 当前走行业默认模板（未显式配置）
      "reasons": [str],           # F4 透明标注：推荐依据（不伪装“智能”）
    }]

🔴 隐私红线（MASTER §S3）：
- interest 仅来自本租户画像 + 本租户 BOM + 本租户行业变量，绝不跨租户。
- 纯函数打分：build_tenant_interest / recommend_sources 无副作用、不触碰其他租户数据。
- 推荐呈 draft 形式（reasons 透明），由人审后在前端点「订阅」落盘——绝不静默自动订阅。
"""

from __future__ import annotations

import os

# 复用 S3-2 的类目→agent 映射（反向推：agent 使用 → 类目兴趣）
from src.runtime.signal_relevance import CATEGORY_AGENT_MAP, SOURCE_NAME_CATEGORY

# ---------- 行业关键词 → env 类目（默认兴趣）----------
INDUSTRY_CATEGORY_HINTS: dict[str, list[str]] = {
    "制造": ["policy", "market", "benchmark"],
    "装备": ["market", "benchmark"],
    "电子": ["market", "benchmark"],
    "半导体": ["market", "benchmark"],
    "汽车": ["market", "policy", "benchmark"],
    "新能源": ["market", "policy"],
    "电池": ["market", "policy"],
    "光伏": ["market", "policy"],
    "化工": ["market", "policy"],
    "医药": ["policy", "benchmark"],
    "食品": ["policy", "benchmark"],
    "材料": ["market"],
    "钢铁": ["market", "policy"],
    "纺织": ["market", "policy"],
    "机械": ["market", "benchmark"],
    "金属": ["market"],
    "塑料": ["market"],
}

# ---------- BOM 物料名关键词 → env 类目（启发式）----------
MATERIAL_MARKET_KW = [
    "硅", "铜", "铝", "锂", "钢", "铁", "塑料", "树脂", "橡胶", "化工", "石油",
    "稀土", "钛", "镍", "钴", "锰", "矿", "芯片", "晶圆", "电子", "电池", "光伏",
    "玻", "水泥", "木材", "纸", "漆", "涂料", "胶", "膜", "线", "纱", "纤维",
    "不锈钢", "合金", "镀", "碳", "氢", "氨", "树脂", "聚乙烯", "聚丙烯", "pcb",
    "pcba", "led", "传感器", "电机", "阀门", "泵", "轴承", "线缆",
]
MATERIAL_POLICY_KW = [
    "安全", "环保", "排放", "法规", "认证", "标准", "资质", "危化", "回收",
    "碳", "能耗", "绿色", "合规", "消防", "职业卫生", "排污", "许可",
]
MATERIAL_BENCHMARK_KW = [
    "数字化", "智能", "自动", "工业4", "工业5", "灯塔", "精益", "质量",
    "标杆", "转型", "mes", "erp", "数字孪生", "工业互联网", "机器人", "ai",
]

# ---------- 打分常量（常量化，便于治理）----------
AGENT_USAGE_WEIGHT = 0.7     # 常用某类目智能体 → 该类目源推荐度
BOM_MATERIAL_WEIGHT = 0.7    # BOM 物料命中类目关键词 → 该类目源推荐度
INDUSTRY_DEFAULT_WEIGHT = 0.6  # 行业默认关注类目 → 基线推荐度
GENERIC_BASELINE = 0.5       # 无任何证据 → 通用基础订阅（不遗漏）
SUPPRESS_FLOOR = 0.1         # 推荐度下限（防止完全 0 分，仍可按需人工开启）


def _agent_to_category() -> dict[str, str]:
    """反向映射：agent → 它主要服务的 env 类目（取权重最高的类目）。"""
    m: dict[str, str] = {}
    for cat, agents in CATEGORY_AGENT_MAP.items():
        for a, _w in agents:
            # 一个 agent 可能出现在多类目；首见优先（权重最高的类目先注册）
            m.setdefault(a, cat)
    return m


def build_tenant_interest(
    profile: dict | None, materials: list[str] | None, industry: str | None
) -> dict:
    """从本租户行为画像 + BOM 物料 + 行业 派生「类目兴趣」与透明证据。

    返回 {
      "category_interests": {cat: float},   # 类目推荐度（未归一，供推荐打分取 max）
      "material_terms": set[str],           # BOM 物料关键词（透明证据，前端展示）
      "material_by_category": {cat: [mat]}, # 命中类目关键词的物料（按类目，透明）
      "agent_by_category": {cat: [agent]},  # 常用智能体（按类目，透明）
      "industry_categories": set[str],      # 行业默认关注类目
    }

    🔴 仅本租户数据；materials 应为本租户 BOM 物料列表（调用方已隔离）。
    """
    category_interests: dict[str, float] = {}
    material_terms: set[str] = set()
    material_by_category: dict[str, list[str]] = {}
    agent_by_category: dict[str, list[str]] = {}
    industry_categories: set[str] = set()

    agent_map = _agent_to_category()

    # 1) 行为画像：top_objects 中 object_kind="agent" → 反推类目兴趣
    if profile:
        for obj in profile.get("top_objects", []) or []:
            oid = obj.get("object") if isinstance(obj, dict) else str(obj)
            if oid and oid.startswith("agent:"):
                agent = oid.split(":", 1)[1]
                cat = agent_map.get(agent)
                if cat:
                    category_interests[cat] = max(
                        category_interests.get(cat, 0.0), AGENT_USAGE_WEIGHT
                    )
                    agent_by_category.setdefault(cat, [])
                    if agent not in agent_by_category[cat]:
                        agent_by_category[cat].append(agent)

    # 2) BOM 物料名：关键词启发式 → 类目 + 透明物料证据
    for raw in materials or []:
        mat = (raw or "").strip()
        if not mat:
            continue
        material_terms.add(mat)
        low = mat.lower()
        for kw in MATERIAL_MARKET_KW:
            if kw in low:
                category_interests["market"] = max(
                    category_interests.get("market", 0.0), BOM_MATERIAL_WEIGHT
                )
                material_by_category.setdefault("market", [])
                if mat not in material_by_category["market"]:
                    material_by_category["market"].append(mat)
                break
        for kw in MATERIAL_POLICY_KW:
            if kw in low:
                category_interests["policy"] = max(
                    category_interests.get("policy", 0.0), BOM_MATERIAL_WEIGHT
                )
                material_by_category.setdefault("policy", [])
                if mat not in material_by_category["policy"]:
                    material_by_category["policy"].append(mat)
                break
        for kw in MATERIAL_BENCHMARK_KW:
            if kw in low:
                category_interests["benchmark"] = max(
                    category_interests.get("benchmark", 0.0), BOM_MATERIAL_WEIGHT
                )
                material_by_category.setdefault("benchmark", [])
                if mat not in material_by_category["benchmark"]:
                    material_by_category["benchmark"].append(mat)
                break

    # 3) 行业：关键词命中 → 该类目默认关注（基线）
    ind = (industry or "").strip()
    if ind:
        for kw, cats in INDUSTRY_CATEGORY_HINTS.items():
            if kw.lower() in ind.lower():
                for cat in cats:
                    category_interests[cat] = max(
                        category_interests.get(cat, 0.0), INDUSTRY_DEFAULT_WEIGHT
                    )
                    industry_categories.add(cat)
        # 行业未命中任何关键词 → 三类目均给通用基线（制造型企业默认全关注）
        if not industry_categories:
            for cat in ("policy", "market", "benchmark"):
                category_interests[cat] = max(
                    category_interests.get(cat, 0.0), GENERIC_BASELINE
                )
                industry_categories.add(cat)
    else:
        # 无行业变量 → 通用基线（不遗漏任何官方源）
        for cat in ("policy", "market", "benchmark"):
            category_interests[cat] = max(
                category_interests.get(cat, 0.0), GENERIC_BASELINE
            )
            industry_categories.add(cat)

    return {
        "category_interests": category_interests,
        "material_terms": material_terms,
        "material_by_category": material_by_category,
        "agent_by_category": agent_by_category,
        "industry_categories": industry_categories,
    }


def _score_category(cat: str, interest: dict) -> tuple[list[str], float]:
    """对单个 env 类目打分 + 透明理由。"""
    cat_weights = interest.get("category_interests", {}) or {}
    base = cat_weights.get(cat, 0.0)
    score = base
    reasons: list[str] = []

    mat_for_cat = interest.get("material_by_category", {}).get(cat, []) or []
    if mat_for_cat:
        sample = "、".join(mat_for_cat[:3])
        more = len(mat_for_cat) - 3
        reasons.append(
            f"你的 BOM 含「{sample}」等物料，匹配{cat}类信息源"
            + (f"（共 {len(mat_for_cat)} 项）" if more > 0 else "")
        )
        score = max(score, BOM_MATERIAL_WEIGHT)

    agent_for_cat = interest.get("agent_by_category", {}).get(cat, []) or []
    if agent_for_cat:
        sample = "、".join(agent_for_cat[:3])
        reasons.append(f"你常用 {sample} 等智能体，其解读依赖 {cat} 类情报")
        score = max(score, AGENT_USAGE_WEIGHT)

    if cat in (interest.get("industry_categories", set()) or set()):
        reasons.append("你的行业属性默认关注该类目信息")
        score = max(score, INDUSTRY_DEFAULT_WEIGHT)

    if not reasons:
        reasons.append("通用环境信息源，建议作为基础订阅")
        score = max(score, GENERIC_BASELINE)

    score = min(1.0, max(score, SUPPRESS_FLOOR))
    return reasons, round(score, 3)


def recommend_sources(
    known_sources: list[dict], subscriptions: list[dict], interest: dict
) -> list[dict]:
    """对已知源按租户兴趣打分，产出推荐（含已订阅确认）。

    known_sources：env_manager.list() 的源 status 列表（含 name/kind/label/credibility）。
    subscriptions：env_subscription_store.list_for(tenant) 输出。
    interest：build_tenant_interest 产物。

    返回按推荐度降序；subscribed=是否已启用该源（draft 待审 = 未订阅）。
    """
    sub_state = {s.get("source_name"): s for s in (subscriptions or [])}
    recs: list[dict] = []
    for src in known_sources or []:
        name = src.get("name")
        if not name:
            continue
        cat = SOURCE_NAME_CATEGORY.get(name)
        if not cat:
            continue  # 仅对已知映射的 env 源做推荐（扩展源自动纳入）
        reasons, score = _score_category(cat, interest)
        sub = sub_state.get(name)
        subscribed = bool(sub and sub.get("enabled"))
        recs.append({
            "source_name": name,
            "kind": src.get("kind", cat),
            "label": src.get("label", name),
            "credibility": src.get("credibility", "general"),
            "category": cat,
            "score": score,
            "subscribed": subscribed,
            "is_default": bool(sub and sub.get("is_default")),
            "reasons": reasons,
        })
    recs.sort(key=lambda r: r["score"], reverse=True)
    return recs


# ---------- S3-4 采纳/驳回反哺（#318，与蓝弧后果回流同构）----------

REJECT_FLOOR = 0.12  # 驳回的源/类目 → 推荐度压到该下限（仍可撤销，不静默消失）


def apply_feedback(recs: list[dict], adjustments: dict) -> tuple[list[dict], bool]:
    """将本租户采纳/驳回反馈回流到推荐打分（F4 透明标注；🔴 仅本租户反馈）。

    adjustments：recommendation_feedback_store.adjustments_for(tenant) 产物。
    - 驳回的源 / 类目 → 推荐度压到 REJECT_FLOOR，标记 rejected=True，附透明理由（可撤销）。
    - 采纳强化类目 → 该类目源推荐度 +对应 boost（封顶 1.0），附透明理由。

    返回 (调整后推荐列表[按 score 降序], 是否应用了任何反馈)。
    """
    cat_boost = (adjustments or {}).get("category_boost", {}) or {}
    rejected_sources = set((adjustments or {}).get("rejected_sources", []) or [])
    rejected_cats = set((adjustments or {}).get("rejected_categories", []) or [])
    applied = bool(cat_boost or rejected_sources or rejected_cats)

    out: list[dict] = []
    for rec in recs or []:
        r = dict(rec)
        r["rejected"] = False
        rejected = (r.get("source_name") in rejected_sources) or (r.get("category") in rejected_cats)
        if rejected:
            r["rejected"] = True
            r["score"] = min(r.get("score", 1.0), REJECT_FLOOR)
            reason = "你曾驳回此主题推荐，已下调推荐度（可撤销）"
            if reason not in r["reasons"]:
                r["reasons"] = list(r["reasons"]) + [reason]
        elif r.get("category") in cat_boost:
            boost = cat_boost[r["category"]]
            r["score"] = min(1.0, round((r.get("score", 0.0) + boost), 3))
            reason = "你曾采纳同类信息源，已上调推荐度"
            if reason not in r["reasons"]:
                r["reasons"] = list(r["reasons"]) + [reason]
        out.append(r)

    out.sort(key=lambda x: x["score"], reverse=True)
    return out, applied
