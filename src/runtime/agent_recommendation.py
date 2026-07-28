"""S3-5 行为导航④（无感转型导航器，#319）

按租户自身产品内行为（绝不引入外部画像）推荐下一值得解锁的智能体——
关注重点 → 三圈地图上的最短价值路径。

信号来源（全部本租户，🔴 绝不跨租户）：
- 高频查看/使用的智能体（behavior_store.profile.top_objects 中 agent: 前缀）
- 关注的环境情报类目（policy/market/benchmark，由 S3-3 build_tenant_interest 派生：
  agent 使用 → 类目、BOM 物料关键词 → 类目、行业 → 默认类目）
- 情报采纳记录（S3-4 已采纳的源类目 → 强化该类目关注）

推荐纪律（MASTER §S3-5）：
- 推荐语必须以价值句式呈现：「你关注的 X，配合 Y，{agent} 能算出 Z」。
  绝不用功能列表句式（"XX agent 提供 YY 功能" 一律禁止）。
- 走 F4 透明标注：每条推荐附 reasons（基于你最近的哪些行为），明示为租户自身行为派生。
- 融入「解锁进度」三圈视图：只推荐当前圈层之外的「下一步」agent（锁定态），
  相邻呈现、不弹窗、不打断（与 §3.5 纪律 3 同构）。
- 隐私边界：行为画像仅存于本租户、仅用于本租户推荐，绝不跨租户聚合到个体可识别粒度。

输出 recommend_next_agents：
    [{
      "agent": str,            # agent id（下一圈、锁定态）
      "label": str,            # 友好名
      "circle": str,           # 所属圈层（= 下一圈）
      "score": float,          # 与关注重点的匹配度 [0,1]（仅排序用）
      "value_sentence": str,   # F4 价值句式「你关注的 X，配合 Y，能算出 Z」
      "reasons": [str],        # F4 透明标注：推荐依据
      "locked": bool,          # True=需完成下一步解锁（总是 True，除非已 inner）
      "source": "behavior",     # 明示为租户自身行为派生（非共享平台建议）
    }]
"""

from __future__ import annotations

from src.runtime.signal_relevance import CATEGORY_AGENT_MAP

# ---------- 环境类目 → 价值句式中的「你关注的 X」 ----------
CATEGORY_FOCUS_PHRASE: dict[str, str] = {
    "market": "原材料行情与供应链波动",
    "policy": "政策合规动向",
    "benchmark": "行业智能化对标",
}

# ---------- 三圈成员（与 unlock_map 对齐；外圈免费已可用，不推荐） ----------
MIDDLE_AGENTS = ["cost_analysis", "demand_order", "bom_selector", "rd_npi"]
INNER_AGENTS = [
    "pm_maintenance", "yield_analysis", "quality_trace", "dfm_check",
    "oee_optimizer", "eco_change", "smt_changeover", "aoi_judge",
    "ipc_standard", "aps_scheduler", "energy_carbon", "wms_logistics",
]
_AGENT_CIRCLE: dict[str, str] = {}
for _a in MIDDLE_AGENTS:
    _AGENT_CIRCLE[_a] = "middle"
for _a in INNER_AGENTS:
    _AGENT_CIRCLE[_a] = "inner"

# ---------- 每个「下一步」agent 的价值映射 ----------
# serves_categories：该 agent 服务于哪些环境类目（用于匹配用户关注）
# input：价值句式中的「配合 Y」（需投入的数据）
# output：价值句式中的「能算出 Z」（产出价值）
AGENT_VALUE_MAP: dict[str, dict] = {
    # —— 中圈（外部×内部交叉）——
    "cost_analysis": {
        "label": "成本分析", "serves_categories": ["market"],
        "input": "上传一份 BOM", "output": "实时毛利影响与成本构成分析",
    },
    "demand_order": {
        "label": "需求订单", "serves_categories": ["market"],
        "input": "接入订单与需求数据", "output": "需求预测与智能备货建议",
    },
    "bom_selector": {
        "label": "BOM 选型", "serves_categories": ["benchmark", "market"],
        "input": "提供设计 BOM 与规格", "output": "可采购替代料与选型风险清单",
    },
    "rd_npi": {
        "label": "研发 NPI", "serves_categories": ["benchmark"],
        "input": "导入新品 BOM 与工艺", "output": "NPI 可制造性评估与量产风险",
    },
    # —— 内圈（深度自治）——
    "pm_maintenance": {
        "label": "设备维护", "serves_categories": ["benchmark"],
        "input": "接入设备运行数据", "output": "预测性维护计划与停机预警",
    },
    "yield_analysis": {
        "label": "良率分析", "serves_categories": ["benchmark"],
        "input": "汇聚生产质量数据", "output": "良率根因分析与改进建议",
    },
    "quality_trace": {
        "label": "质量追溯", "serves_categories": ["benchmark"],
        "input": "打通批次与工艺数据", "output": "全链路质量追溯与召回定位",
    },
    "dfm_check": {
        "label": "DFM 可制造性", "serves_categories": ["benchmark"],
        "input": "提交设计图纸与 BOM", "output": "可制造性（DFM）风险清单",
    },
    "oee_optimizer": {
        "label": "OEE 优化", "serves_categories": ["benchmark"],
        "input": "采集设备与排产数据", "output": "OEE 提升方案与瓶颈诊断",
    },
    "eco_change": {
        "label": "环保合规", "serves_categories": ["policy"],
        "input": "接入排放与能耗数据", "output": "绿色合规改进路径与碳排核算",
    },
    "smt_changeover": {
        "label": "SMT 换线", "serves_categories": ["benchmark"],
        "input": "接入 SMT 产线数据", "output": "快速换线（换型）优化方案",
    },
    "aoi_judge": {
        "label": "AOI 判定", "serves_categories": ["benchmark"],
        "input": "导入 AOI 图像与判定标准", "output": "缺陷自动判定与分级",
    },
    "ipc_standard": {
        "label": "IPC 标准", "serves_categories": ["policy"],
        "input": "对接工艺与 IPC 标准库", "output": "标准符合性诊断与整改清单",
    },
    "aps_scheduler": {
        "label": "排产调度", "serves_categories": ["benchmark"],
        "input": "接入订单与产能约束", "output": "最优排产计划与交期保障",
    },
    "energy_carbon": {
        "label": "能耗碳排", "serves_categories": ["policy"],
        "input": "汇聚能源与碳数据", "output": "碳足迹核算与节能降耗方案",
    },
    "wms_logistics": {
        "label": "仓储物流", "serves_categories": ["market"],
        "input": "接入库存与出入库数据", "output": "仓储优化与配送调度建议",
    },
}

# ---------- 打分常量（常量化，便于治理） ----------
AGENT_USAGE_WEIGHT = 0.7    # 常用某类目智能体 → 该类目关注权重
ADOPT_BOOST = 0.15          # S3-4 已采纳某类目源 → 该类目关注 +boost
BASELINE_FOCUS = 0.3        # 无行为信号时，各类目基线关注（保证下一圈 agent 仍被推荐）
TOP_N = 3                   # 前端「推荐下一步」最多展示条数


def _agent_to_category() -> dict[str, str]:
    """反向映射：agent → 它主要服务的 env 类目（取首个注册类目）。"""
    m: dict[str, str] = {}
    for cat, agents in CATEGORY_AGENT_MAP.items():
        for a, _w in agents:
            m.setdefault(a, cat)
    return m


def build_focus(
    profile: dict | None,
    category_interests: dict[str, float] | None,
    adopted_categories: list[str] | None = None,
) -> dict:
    """从本租户行为画像 + 类目兴趣 + 已采纳类目 派生「关注重点」。

    返回 {
      "focus_categories": {cat: float},  # 各类目关注权重（供匹配下一圈 agent）
      "signals": [str],                  # F4 透明：派生所用的行为信号（前端展示）
    }

    🔴 仅本租户数据；profile/category_interests/adopted_categories 调用方已隔离。
    """
    focus_categories: dict[str, float] = {}
    signals: list[str] = []

    agent_map = _agent_to_category()

    # 1) 行为画像：top_objects 中 agent: 前缀 → 反推类目兴趣
    if profile:
        for obj in profile.get("top_objects", []) or []:
            oid = obj.get("object") if isinstance(obj, dict) else str(obj)
            if oid and oid.startswith("agent:"):
                agent = oid.split(":", 1)[1]
                cat = agent_map.get(agent)
                if cat:
                    prev = focus_categories.get(cat, 0.0)
                    focus_categories[cat] = max(prev, AGENT_USAGE_WEIGHT)
                    signals.append(f"你常用 {agent}（关注{cat}类）")

    # 2) 类目兴趣（S3-3 派生：agent 使用 + BOM 物料 + 行业）
    for cat, w in (category_interests or {}).items():
        focus_categories[cat] = max(focus_categories.get(cat, 0.0), float(w))

    # 3) S3-4 已采纳类目 → 强化关注
    for cat in adopted_categories or []:
        if cat in ("policy", "market", "benchmark"):
            prev = focus_categories.get(cat, 0.0)
            focus_categories[cat] = min(1.0, max(prev, 0.5) + ADOPT_BOOST)
            signals.append(f"你已采纳{cat}类信息源")

    # 无信号 → 基类目基线（保证下一圈 agent 仍被推荐，不静默空窗）
    if not focus_categories:
        for cat in ("policy", "market", "benchmark"):
            focus_categories[cat] = BASELINE_FOCUS
        signals.append("暂无明确行为信号，按通用关注推荐")

    return {"focus_categories": focus_categories, "signals": signals}


def _value_sentence(agent: str, focus_categories: dict[str, float]) -> tuple[str, str]:
    """构造 F4 价值句式「你关注的 X，配合 Y，{label} 能算出 Z」。

    返回 (value_sentence, matched_category)。匹配用户关注权重最高的 serves 类目作为 X。
    """
    meta = AGENT_VALUE_MAP[agent]
    serves = meta["serves_categories"]
    # 选用户关注权重最高的 serves 类目
    best_cat = None
    best_w = -1.0
    for cat in serves:
        w = focus_categories.get(cat, 0.0)
        if w > best_w:
            best_w = w
            best_cat = cat
    phrase = CATEGORY_FOCUS_PHRASE.get(best_cat or serves[0], "业务重点")
    sentence = (
        f"你关注的{phrase}，配合{meta['input']}，{meta['label']} 能算出{meta['output']}。"
    )
    return sentence, (best_cat or serves[0])


def recommend_next_agents(
    current_circle: str,
    focus: dict,
    limit: int = TOP_N,
) -> list[dict]:
    """推荐当前圈层之外的「下一步」agent（锁定态），按与关注重点匹配度降序。

    current_circle：outer/middle/inner（来自 unlock_map.current_circle）。
    若已 inner（全解锁）→ 返回空列表（无下一步可推）。

    每条推荐附 F4 价值句式 + 透明 reasons + locked=True。
    """
    _CIRCLE_RANK = {"outer": 0, "middle": 1, "inner": 2}
    cur_rank = _CIRCLE_RANK.get(current_circle, 0)
    if cur_rank >= 2:
        return []  # 已全解锁

    focus_categories = (focus or {}).get("focus_categories", {}) or {}
    focus_signals = (focus or {}).get("signals", []) or []

    candidates = [a for a in AGENT_VALUE_MAP if _CIRCLE_RANK[_AGENT_CIRCLE[a]] > cur_rank]
    if not candidates:
        return []

    scored: list[tuple[float, str]] = []
    for agent in candidates:
        meta = AGENT_VALUE_MAP[agent]
        match = max((focus_categories.get(c, 0.0) for c in meta["serves_categories"]), default=0.0)
        scored.append((match, agent))
    # 按匹配度降序；同分按价值映射注册序（中圈先于内圈）
    scored.sort(key=lambda x: (-x[0], candidates.index(x[1])))

    recs: list[dict] = []
    for match, agent in scored[: max(1, limit)]:
        meta = AGENT_VALUE_MAP[agent]
        sentence, matched_cat = _value_sentence(agent, focus_categories)
        reasons = list(focus_signals) or ["基于你当前的使用习惯推荐"]
        reasons = reasons + [f"该智能体服务你关注的{matched_cat}类主题"]
        recs.append({
            "agent": agent,
            "label": meta["label"],
            "circle": _AGENT_CIRCLE[agent],
            "score": round(min(1.0, max(match, 0.0)), 3),
            "value_sentence": sentence,
            "reasons": reasons,
            "locked": True,
            "source": "behavior",
        })
    return recs


def recommend_for_tenant(tenant_id: str) -> dict:
    """S3-5 租户级管线：画像 + BOM + 行业 + 已采纳 → 关注 → 下一步 agent 推荐。

    纯读取（无副作用）；🔴 严格租户隔离：所有输入均来自本租户存储。
    返回 {tenant_id, current_circle, recommended_next:[...]}。
    """
    from src.runtime.behavior_store import behavior_store
    from src.runtime.bom_store import bom_store
    from src.runtime.source_recommendation import build_tenant_interest
    from src.runtime.recommendation_feedback_store import adjustments_for
    from src.runtime.unlock_map import current_circle

    circle = current_circle(tenant_id)
    if circle == "inner":
        return {"tenant_id": tenant_id, "current_circle": circle, "recommended_next": []}

    profile = behavior_store.profile(tenant_id)

    # 本租户 BOM 全量物料（list_for 已剔除 items，需逐份 get 取回物料名）
    materials: list[str] = []
    for rec in bom_store.list_for(tenant_id):
        full = bom_store.get(tenant_id, rec["id"])
        for it in (full or {}).get("items", []) or []:
            m = it.get("material")
            if m:
                materials.append(str(m))

    import os
    industry = (os.getenv("ZHIYAN_INDUSTRY", "") or "").strip()

    interest = build_tenant_interest(profile, materials, industry)
    adopted = adjustments_for(tenant_id).get("category_boost", {}) or {}
    adopted_cats = [c for c in adopted.keys() if c in ("policy", "market", "benchmark")]

    focus = build_focus(profile, interest["category_interests"], adopted_cats)
    recs = recommend_next_agents(circle, focus)
    return {"tenant_id": tenant_id, "current_circle": circle, "recommended_next": recs}
