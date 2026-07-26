"""v22.5 孪生大屏 API —— 聚合全息数据用于三主义一体可视化大屏

汇聚五路数据源为一个大屏可消费的结构：
- UNS 近期事件 + 通道统计
- KG 事实提议管线（待审批 / 已审批 / 需复审 / 纠错）
- 蓝弧闭环统计 + 近期校验记录
- 经验库概览（总记录 / 隐性捕获 / 后果反馈）
- 网关连接状态
"""

from fastapi import APIRouter

from src.runtime.uns import uns
from src.runtime.experience import experience
from src.runtime.evolution.kg_facts import kg_facts

router = APIRouter(prefix="/twin", tags=["twin"])


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
