"""v24.0 跨企业联邦学习 API

端点：
- GET  /federation/patterns      — 跨租户 KG 模式聚合
- GET  /federation/patterns/high — 高联邦可信度模式（可建议给其他租户）
- GET  /federation/strategy      — 跨租户策略信号聚合
- GET  /federation/status        — 联邦学习健康状态
"""

from fastapi import APIRouter

from src.runtime.federation.federated_kg import federated_kg
from src.runtime.federation.federated_strategy import federated_strategy

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
