"""v22.5 孪生大屏 API —— 聚合全息数据用于三主义一体可视化大屏

汇聚五路数据源为一个大屏可消费的结构：
- UNS 近期事件 + 通道统计
- KG 事实提议管线（待审批 / 已审批 / 需复审 / 纠错）
- 蓝弧闭环统计 + 近期校验记录
- 经验库概览（总记录 / 隐性捕获 / 后果反馈）
- 网关连接状态
"""

from fastapi import APIRouter

from src.runtime.uns import uns, CHANNEL_ENVIRONMENT
from src.runtime.experience import experience
from src.runtime.evolution.kg_facts import kg_facts
from src.runtime.env_sources.manager import env_manager
from src.runtime.env_perception import env_review
from src.runtime.signal_relevance import SOURCE_NAME_CATEGORY

router = APIRouter(prefix="/twin", tags=["twin"])

# 体外感知（第⑥路环境感知）类目 → 大屏友好名（六维感知覆盖）
_CATEGORY_LABELS = {
    "policy": "政策法规",
    "market": "原材料行情",
    "benchmark": "行业对标",
    "competitor": "竞品动态",
    "supplychain": "供应链风险",
    "customervoice": "客户声音",
}
_CREDIBILITY_LABELS = {
    "official": "官方",
    "authoritative": "权威",
    "general": "一般",
    "platform": "平台建议",
}


@router.get("/dashboard")
async def twin_dashboard():
    """全息孪生大屏 —— 三主义一体可视化数据聚合。"""
    from src.runtime.consequence import consequence

    kg_proposals = kg_facts.list_proposals()

    # 网关状态（韧性降级：manager 不可达时返回空字典）
    try:
        from src.gateways.manager import manager as gw_manager

        gw_health = await gw_manager.health()
    except Exception:
        gw_health = {}

    return {
        "uns": {
            "channel_counts": uns.channel_counts(),
            "recent_events": uns.recent(20),
            "total_events": len(uns._events),
        },
        "kg": {
            "total_proposals": len(kg_proposals),
            "drafts": len([p for p in kg_proposals if p["status"] == "draft"]),
            "approved": len([p for p in kg_proposals if p["status"] == "approved"]),
            "needs_review": len([p for p in kg_proposals if p["status"] == "needs_review"]),
            "validated": len([p for p in kg_proposals if p["status"] == "validated"]),
            "corrections": len([p for p in kg_proposals if p.get("corrects")]),
            "recent_proposals": [
                {
                    "id": p["id"],
                    "status": p["status"],
                    "subject": p["subject"],
                    "predicate": p["predicate"],
                    "object_val": p["object_val"],
                    "confidence": p.get("confidence", 0),
                }
                for p in kg_proposals[-10:]
            ],
        },
        "consequence": {
            "stats": consequence.stats(),
            "recent": consequence.query(limit=10),
        },
        "experience": {
            "total_records": len(experience._records),
            "feedback": len([r for r in experience._records if r.get("kind") not in ("tacit", "outcome", "captured")]),
            "tacit_captures": len(
                [r for r in experience._records if r.get("kind") == "tacit"]
            ),
            "outcomes": len([r for r in experience._records if r.get("kind") == "outcome"]),
        },
        "gateways": gw_health,
    }


# ============ S3-7 体外感知大屏视图（#321，第⑥路环境感知全息化） ============


@router.get("/external-perception")
async def external_perception():
    """孪生大屏「体外感知」视图数据聚合（#321，MASTER §S3-7）。

    把第⑥路环境感知（封闭系统→物理世界开放系统：政策/行情/对标/竞品/供应链/客户声音）
    全息化为大屏可消费的聚合结构，与孪生大屏其余区块同构（租户不可知的全息视图）：

    - signal_count：体外信号总量（UNS environment 路，跨租户共享信号池）
    - category_distribution：六维感知覆盖（按信号类目聚合，F4 透明）
    - credibility_distribution：可信度分级分布（官方为锚的可信治理可视化）
    - sources：三官方源健康（policy/market/benchmark，running/mode/last_pull）
    - review：非官方信号人工审核队列（_needs_review 治理门计数）
    - recent_signals：最近高相关体外信号（title/source/credibility/category）

    韧性降级：env_manager / env_review 不可达时返回空结构，不破管。
    """
    try:
        # 🔴 过滤 internal_only 源（如 disclosure 上铁实证）：仅内部研究实测，绝不出现在外界可见的孪生大屏
        sources = [s for s in env_manager.list() if not s.get("internal_only", False)]
    except Exception:
        sources = []

    try:
        review = env_review.counts()
    except Exception:
        review = {}

    signals = uns.query(channel=CHANNEL_ENVIRONMENT, n=1000)

    cat_dist: dict[str, int] = {}
    cred_dist: dict[str, int] = {}
    for s in signals:
        payload = s.get("payload") or {}
        raw_cat = payload.get("category") or SOURCE_NAME_CATEGORY.get(s.get("source", ""), s.get("source", ""))
        cat = str(raw_cat) if raw_cat else "other"
        cat_dist[cat] = cat_dist.get(cat, 0) + 1
        cred = s.get("credibility") or "general"
        cred_dist[cred] = cred_dist.get(cred, 0) + 1

    # 最近信号（按时间倒序，取前 12 条；字段裁剪仅保留大屏所需）
    recent = sorted(signals, key=lambda x: x.get("ts", 0), reverse=True)[:12]
    recent_signals = [
        {
            "id": s.get("id"),
            "source": s.get("source"),
            "credibility": s.get("credibility"),
            "category": (s.get("payload") or {}).get("category")
            or SOURCE_NAME_CATEGORY.get(s.get("source", ""), s.get("source", "")),
            "title": (s.get("payload") or {}).get("title", ""),
            "ts": s.get("ts"),
        }
        for s in recent
    ]

    return {
        "signal_count": len(signals),
        "category_distribution": cat_dist,
        "credibility_distribution": cred_dist,
        "category_labels": _CATEGORY_LABELS,
        "credibility_labels": _CREDIBILITY_LABELS,
        "sources": sources,
        "review": {
            "pending": review.get("pending", 0),
            "approved": review.get("approved", 0),
            "rejected": review.get("rejected", 0),
            "total": review.get("total", 0),
        },
        "recent_signals": recent_signals,
    }
