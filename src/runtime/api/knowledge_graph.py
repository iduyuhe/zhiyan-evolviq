"""知识图谱 API——跨 Agent 语义网查询与构建"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.common import neo4j_client as neo
from src.runtime import knowledge_graph as kg
from src.runtime.authn.deps import require_auth
from src.runtime.context import get_current_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kg", tags=["knowledge-graph"])

# SUPERADMIN 角色名（与 roles.py 一致）
_SUPERADMIN_ROLES = ("superadmin", "SUPERADMIN")


def _effective_tenant(tenant: str | None, u: dict) -> str | None:
    """多租户隔离：非超级管理员忽略客户端 tenant 参数（杜绝越权读他租户），
    仅 SUPERADMIN 可显式指定租户跨看。

    注：种子参考图谱未打 tenant 标签，故非超级管理员缺省仍返回全量（含共享参考图谱），
    以保留 dev 展示行为；S2 对外前需把种子打标 tenant="default" 并默认按当前租户隔离。
    """
    if tenant and u.get("role") in _SUPERADMIN_ROLES:
        return tenant
    return None


class RebuildResponse(BaseModel):
    mode: str
    stats: dict


@router.get("/stats")
async def graph_stats():
    """图谱统计：节点/边总数、按类型分布、存储模式（neo4j / memory）。"""
    stats = await neo.graph_stats()
    return {"mode": neo.neo_mode, "available": neo.neo_available, **stats}


@router.get("/query")
async def query(
    label: str | None = Query(None, description="节点类型，如 Material/Equipment/Product/DefectCase"),
    node_id: str | None = Query(None, description="全局节点 id，如 Equipment:scanner_1"),
    edge: str | None = Query(None, description="关系类型过滤，如 有部件/包含/怀疑设备"),
    direction: str = Query("out", description="out / in / any"),
    category: str | None = Query(None, description="属性过滤，如 Material.category=三极管"),
    name: str | None = Query(None, description="name 属性过滤"),
    tenant: str | None = Query(None, description="按租户隔离查询（仅 SUPERADMIN 可指定；非管理员忽略此参数）"),
    u: dict = Depends(require_auth),
):
    """预定义查询：按 label + 属性过滤节点，或按 node_id 查邻居。

    多租户隔离：非 SUPERADMIN 的 tenant 参数被忽略，无法读取其他租户图谱（防越权）。
    """
    eff = _effective_tenant(tenant, u)
    try:
        if node_id:
            return {"tenant": eff, "node_id": node_id, "neighbors": await neo.get_neighbors(node_id, edge, direction, tenant=eff)}
        if label:
            filters = {}
            if category:
                filters["category"] = category
            if name:
                filters["name"] = name
            return {"tenant": eff, "label": label, "nodes": await neo.query_nodes(label, tenant=eff, **filters)}
        return {"hint": "需提供 label（列节点）或 node_id（查邻居）"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild", response_model=RebuildResponse)
async def rebuild():
    """从种子数据重建跨 Agent 知识图谱。"""
    stats = await kg.rebuild()
    return RebuildResponse(mode=neo.neo_mode, stats=stats)


@router.get("/recall")
async def recall(
    goal: str = Query(..., description="自然语言目标，用于召回相关历史经验"),
    tenant: str | None = Query(None, description="按租户隔离（仅 SUPERADMIN 可指定；非管理员忽略）"),
    limit: int = Query(5, description="返回条数上限"),
    u: dict = Depends(require_auth),
):
    """经验记忆召回：按目标召回相关历史 Insight（跨 Agent 经验记忆闭环读回）。

    供 Agent 推理前读回历史经验，也供前端/调试查看"系统记住了什么"。
    多租户隔离：非 SUPERADMIN 忽略 tenant 参数，按当前租户召回。
    """
    from src.runtime.memory import recall as _recall
    eff = _effective_tenant(tenant, u) or get_current_tenant()
    return await _recall(goal, tenant_id=eff, limit=limit)
