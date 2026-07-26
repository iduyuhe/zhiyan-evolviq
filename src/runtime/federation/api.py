"""v24.0 跨企业联邦学习 API + v27.0 产业链智能体联邦 API

端点：
- GET  /federation/patterns              — 跨租户 KG 模式聚合
- GET  /federation/patterns/high         — 高联邦可信度模式
- GET  /federation/strategy              — 跨租户策略信号聚合
- GET  /federation/status                — 联邦学习健康状态
- POST /federation/supply-chain/goal     — 共享产业链目标 (v27)
- POST /federation/supply-chain/goal/{id}/join  — 加入目标 (v27)
- GET  /federation/supply-chain/goals    — 列出活跃目标 (v27)
- POST /federation/supply-chain/risk     — 报告跨企业风险 (v27)
- GET  /federation/supply-chain/risks    — 聚合风险视图 (v27)
- POST /federation/supply-chain/plan     — 创建联合计划 (v27)
- GET  /federation/supply-chain/fed-status — 产业链联邦状态 (v27)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.runtime.federation.federated_kg import federated_kg
from src.runtime.federation.federated_strategy import federated_strategy
from src.runtime.federation.supply_chain_federation import federated_supply_chain

router = APIRouter(prefix="/federation", tags=["federation"])


@router.get("/patterns")
async def federated_patterns():
    """跨租户 KG 事实模式聚合（去标识化结构模式）。"""
    return federated_kg.aggregate()


@router.get("/patterns/high")
async def high_trust_patterns(min_trust: float = 0.6):
    """高联邦可信度模式（可用于跨租户建议）。"""
    return {
        "min_trust": min_trust,
        "patterns": federated_kg.high_trust_patterns(min_trust=min_trust),
    }


@router.get("/strategy")
async def federated_strategy_endpoint():
    """跨租户策略信号聚合（匿名统计）。"""
    return federated_strategy.aggregate()


@router.get("/status")
async def federation_status():
    """联邦学习健康状态。"""
    from src.runtime.tenant_store import tenant_store

    tenants = tenant_store.list()
    active_count = sum(1 for t in tenants if getattr(t, "is_active", True))
    patterns = federated_kg.aggregate()
    strategy = federated_strategy.aggregate()

    return {
        "status": "active",
        "tenants": {
            "total": len(tenants),
            "active": active_count,
        },
        "kg_patterns": patterns.get("summary", {}),
        "strategy": strategy.get("summary", {}),
        "federated_agents": list(strategy.get("agent_signals", {}).keys()),
    }


# ========== v27.0 产业链智能体联邦 ==========


class ShareGoalRequest(BaseModel):
    tenant_id: str = "default"
    goal: str
    target_products: list[str] = []
    target_materials: list[str] = []
    urgency: str = "normal"
    deadline: str = ""


class JoinGoalRequest(BaseModel):
    tenant_id: str


class ReportRiskRequest(BaseModel):
    tenant_id: str = "default"
    material: str
    risk_level: str = "medium"
    description: str = ""


class CreatePlanRequest(BaseModel):
    initiator: str = "default"
    goal_id: str
    plan: str


@router.post("/supply-chain/goal")
async def share_supply_chain_goal(req: ShareGoalRequest):
    """共享一个供应链目标到产业链联邦。"""
    federated_supply_chain.register_participant(req.tenant_id)
    return federated_supply_chain.share_goal(
        req.tenant_id, req.goal, req.target_products, req.target_materials,
        req.urgency, req.deadline,
    )


@router.post("/supply-chain/goal/{goal_id}/join")
async def join_supply_chain_goal(goal_id: str, req: JoinGoalRequest):
    """加入一个共享的产业链目标。"""
    result = federated_supply_chain.join_goal(goal_id, req.tenant_id)
    if result is None:
        raise HTTPException(status_code=404, detail="目标不存在或已关闭")
    return {"status": "joined", "goal": result}


@router.get("/supply-chain/goals")
async def list_supply_chain_goals(tenant_id: str | None = None):
    """列出所有活跃的产业链共享目标。"""
    return {"goals": federated_supply_chain.list_active_goals(tenant_id=tenant_id)}


@router.post("/supply-chain/risk")
async def report_supply_chain_risk(req: ReportRiskRequest):
    """企业报告一个供应链风险到联邦（去标识化）。"""
    federated_supply_chain.register_participant(req.tenant_id)
    return federated_supply_chain.report_risk(req.tenant_id, req.material, req.risk_level, req.description)


@router.get("/supply-chain/risks")
async def aggregate_supply_chain_risks():
    """聚合跨企业供应链风险视图（匿名化）。"""
    return federated_supply_chain.aggregate_risks()


@router.post("/supply-chain/plan")
async def create_supply_chain_plan(req: CreatePlanRequest):
    """基于共享目标创建联合执行计划。"""
    federated_supply_chain.register_participant(req.initiator)
    return federated_supply_chain.create_joint_plan(req.initiator, req.goal_id, req.plan)


@router.get("/supply-chain/plans")
async def list_supply_chain_plans(status: str | None = None):
    """列出联合计划。"""
    return {"plans": federated_supply_chain.list_plans(status=status)}


@router.get("/supply-chain/fed-status")
async def supply_chain_federation_status():
    """产业链联邦整体状态。"""
    return federated_supply_chain.federation_status()
