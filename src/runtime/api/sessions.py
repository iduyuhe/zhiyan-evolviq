"""Agent执行会话API——人机交互核心接口"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.runtime.agent.engine import AgentEngine
from src.runtime.persistence import get_session as db_get_session, list_sessions as db_list_sessions
from src.runtime.api.deps import get_tenant
from src.runtime.usage_meter import UsageExceeded, usage_meter

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _meter_insight(tenant: str) -> None:
    """免费额度：agent 解读计量（#309 S2-1b）。

    三个规划入口各计 1 次（/sessions、/quick-check、/multi-agent）；
    超限 402 + 信任爬梯③升级文案。default 租户/已接内部数据源租户免计量。
    """
    try:
        await usage_meter.consume_insight(tenant)
    except UsageExceeded as e:
        raise HTTPException(status_code=402, detail=str(e))


class CreateSessionRequest(BaseModel):
    goal: str
    auth_boundary_id: str | None = None


class ApprovePlanRequest(BaseModel):
    approved: bool
    feedback: str | None = None


class InterventionRequest(BaseModel):
    action: str  # pause, modify_goal, cancel
    new_goal: str | None = None


# 全局单例——AgentEngine在MVP阶段用内存存储会话
_engine = AgentEngine()


def get_engine() -> AgentEngine:
    return _engine


@router.post("/quick-check")
async def quick_check(req: CreateSessionRequest, tenant: str = Depends(get_tenant)):
    """一键快速检查（跳过规划预览，直接执行）"""
    await _meter_insight(tenant)
    engine = get_engine()
    session_id = str(uuid.uuid4())
    plan = await engine.plan(session_id, req.goal, req.auth_boundary_id, tenant_id=tenant)
    result = await engine.execute(session_id, tenant_id=tenant)
    return {
        "tenant_id": tenant,
        "session_id": session_id,
        "status": "completed",
        "result": result,
    }


@router.post("")
async def create_session(req: CreateSessionRequest, tenant: str = Depends(get_tenant)):
    """创建Agent执行会话——人输入目标，Agent开始规划"""
    await _meter_insight(tenant)
    engine = get_engine()
    session_id = str(uuid.uuid4())
    plan = await engine.plan(session_id, req.goal, req.auth_boundary_id, tenant_id=tenant)
    return {
        "tenant_id": tenant,
        "session_id": session_id,
        "status": "awaiting_approval",
        "plan": plan,
    }


@router.post("/{session_id}/approve")
async def approve_plan(session_id: str, req: ApprovePlanRequest, tenant: str = Depends(get_tenant)):
    """人确认/驳回Agent规划"""
    engine = get_engine()
    if req.approved:
        result = await engine.execute(session_id, tenant_id=tenant)
        return {"tenant_id": tenant, "session_id": session_id, "status": "completed", "result": result}
    else:
        await engine.reject(session_id, req.feedback, tenant_id=tenant)
        return {"tenant_id": tenant, "session_id": session_id, "status": "rejected", "feedback": req.feedback}


@router.post("/{session_id}/intervene")
async def intervene(session_id: str, req: InterventionRequest, tenant: str = Depends(get_tenant)):
    """人中途介入"""
    engine = get_engine()
    if req.action == "pause":
        return {"tenant_id": tenant, "session_id": session_id, "status": "paused"}
    elif req.action == "modify_goal" and req.new_goal:
        plan = await engine.plan(session_id, req.new_goal, tenant_id=tenant)
        return {"tenant_id": tenant, "session_id": session_id, "status": "awaiting_approval", "plan": plan}
    elif req.action == "cancel":
        return {"tenant_id": tenant, "session_id": session_id, "status": "cancelled"}
    raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


# ---------------------------------------------------------------------------
# 多 Agent 编排 API（V1-5 缺口补齐：多 Agent 协同 / 跨视角分析）
# ---------------------------------------------------------------------------


@router.post("/multi-agent")
async def create_multi_agent_session(req: CreateSessionRequest, tenant: str = Depends(get_tenant)):
    """创建多 Agent 编排会话：自动分解目标 → 多 Agent 并行规划 → 等人确认。

    与单 Agent 流程的差异：
    - 单 Agent (`/sessions`)：route_goal() → 单一 Agent 生成 plan
    - 多 Agent (`/sessions/multi-agent`)：GoalDecomposer → OrchestratorPlan → 多 Agent 并行规划
    """
    await _meter_insight(tenant)
    engine = get_engine()
    session_id = str(uuid.uuid4())
    plan = await engine.plan_multi(session_id, req.goal, req.auth_boundary_id, tenant_id=tenant)
    return {
        "tenant_id": tenant,
        "session_id": session_id,
        "status": "multi_awaiting_approval",
        "plan": plan,
    }


@router.post("/{session_id}/approve-multi")
async def approve_multi_plan(session_id: str, req: ApprovePlanRequest, tenant: str = Depends(get_tenant)):
    """确认/驳回多 Agent 编排计划。"""
    engine = get_engine()
    if not req.approved:
        # 多 Agent 流程暂不支持完整 reject，简化处理为丢弃
        return {"tenant_id": tenant, "session_id": session_id, "status": "rejected", "feedback": req.feedback}
    report = await engine.execute_multi(session_id, tenant_id=tenant)
    return {
        "tenant_id": tenant,
        "session_id": session_id,
        "status": "multi_completed",
        "report": report,
    }


@router.get("/multi-agent/templates")
async def list_orchestration_templates():
    """列出所有预设编排模板（供前端展示/选择）。"""
    from src.runtime.agent.goal_decomposer import SCENARIO_TEMPLATES
    return {
        "templates": [
            {
                "name": t["name"],
                "triggers": t["triggers"],
                "agents": [a for a, _ in t["agents"]],
                "agent_count": len(t["agents"]),
                "rationale": t["rationale"],
            }
            for t in SCENARIO_TEMPLATES
        ],
        "total": len(SCENARIO_TEMPLATES),
    }


@router.get("/multi-agent/decompose-preview")
async def preview_decomposition(goal: str = Query(..., description="用户目标")):
    """预览目标分解结果（不执行），供前端实时展示「会调用哪些 Agent」。"""
    from src.runtime.agent.goal_decomposer import GoalDecomposer
    decomposer = GoalDecomposer()
    plan = await decomposer.decompose(goal)
    return plan.to_dict()


@router.get("/db")
async def list_sessions_db(limit: int = Query(50, le=200), tenant: str = Depends(get_tenant)):
    """列出当前租户已落库会话（来自数据库，重启后仍可追溯）。须置于 /{session_id} 之前。"""
    rows = await db_list_sessions(limit=limit, tenant_id=tenant)
    return {"tenant_id": tenant, "source": "db", "sessions": rows, "total": len(rows)}


@router.get("/{session_id}/db")
async def get_session_db(session_id: str, tenant: str = Depends(get_tenant)):
    """获取单条已落库会话（来自数据库）。按租户隔离：非本租户会话一律 404（不泄露存在性）。"""
    row = await db_get_session(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found in DB")
    if row.get("tenant_id") != tenant:
        raise HTTPException(status_code=404, detail="Session not found in DB")
    return {"tenant_id": tenant, "source": "db", **row}


@router.get("/{session_id}")
async def get_session(session_id: str, tenant: str = Depends(get_tenant)):
    """获取会话状态"""
    engine = get_engine()
    info = engine.get_session(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"tenant_id": tenant, "session_id": session_id, **info}


@router.get("")
async def list_sessions(tenant: str = Depends(get_tenant)):
    """列出当前租户会话（内存态，来自运行时引擎）"""
    engine = get_engine()
    sessions = engine.list_sessions(tenant_id=tenant)
    return {"tenant_id": tenant, "sessions": sessions, "total": len(sessions)}
