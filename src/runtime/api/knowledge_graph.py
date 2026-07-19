"""知识图谱 API——跨 Agent 语义网查询与构建"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.common import neo4j_client as neo
from src.runtime import knowledge_graph as kg

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


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
):
    """预定义查询：按 label + 属性过滤节点，或按 node_id 查邻居。"""
    try:
        if node_id:
            return {"node_id": node_id, "neighbors": await neo.get_neighbors(node_id, edge, direction)}
        if label:
            filters = {}
            if category:
                filters["category"] = category
            if name:
                filters["name"] = name
            return {"label": label, "nodes": await neo.query_nodes(label, **filters)}
        return {"hint": "需提供 label（列节点）或 node_id（查邻居）"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild", response_model=RebuildResponse)
async def rebuild():
    """从种子数据重建跨 Agent 知识图谱。"""
    stats = await kg.rebuild()
    return RebuildResponse(mode=neo.neo_mode, stats=stats)
