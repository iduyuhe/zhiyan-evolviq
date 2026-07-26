"""经验库 API——偏好/禁忌记忆的对外查询接口（P1 规则自学习闭环）

人类在介入中心审批/驳回 Agent 动作时，反馈被沉淀到经验库
（src.runtime.experience）。本 API 提供按 Agent 查询其「偏好（被采纳）/
禁忌（被驳回）」记忆，供控制台展示与未来 P2 Prompt/RAG 自修订使用。
"""

from fastapi import APIRouter, Depends

from src.runtime.experience import experience
from src.runtime.api.deps import get_tenant

router = APIRouter(prefix="/experience", tags=["experience"])


@router.get("/tacit")
async def tacit_captures(tenant: str = "default", channel: str | None = None, limit: int = 50):
    """隐性捕获查询：人/社交/会议/协作四路经验记忆 + 待审批 KG 事实（抽取即锚定）。"""
    from src.runtime.evolution.kg_facts import kg_facts

    return {
        "tenant_id": tenant,
        "tacit_captures": experience.tacit_captures(tenant=tenant, channel=channel, limit=limit),
        "pending_kg_facts": kg_facts.list_proposals(),
    }


@router.get("/consequence")
async def list_consequences(agent: str | None = None, limit: int = 50):
    """蓝弧闭环：执行后果追踪查询（后果校验记录 + 统计）。"""
    from src.runtime.consequence import consequence as cq

    return {
        "records": cq.query(agent=agent, limit=limit),
        "stats": cq.stats(),
    }


@router.get("/{agent}")
async def agent_experience(agent: str, tenant: str = Depends(get_tenant)):
    """查询某 Agent 的偏好/禁忌经验记忆。"""
    return {
        "tenant_id": tenant,
        "agent": agent,
        "summary": experience.agent_feedback_summary(agent),
        "preferences": experience.get_preferences(agent),
        "forbidden": experience.get_forbidden(agent),
    }


@router.get("")
async def all_experience(limit: int = 100):
    """查询全部经验反馈（最近 limit 条）。"""
    return {"total": len(experience._records), "records": experience.all(limit)}
