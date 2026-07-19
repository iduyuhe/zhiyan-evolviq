"""网关 API——暴露全部工业协议网关的健康与读数（V1-3）

- GET /gateways：聚合健康总览（总数/就绪数/模式分布/逐网关详情）
- GET /gateways/{name}：单网关健康
- POST /gateways/{name}/read：读取网关数据点（address / count）

事实锚点：仅读取真实网关状态，不改写任何业务数据。
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.gateways.manager import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gateways", tags=["gateways"])


class ReadRequest(BaseModel):
    address: str = "*"
    count: int = 10


@router.get("")
async def list_gateways():
    """全部网关健康总览"""
    await manager.ensure_ready()
    return await manager.health()


@router.get("/{name}")
async def gateway_detail(name: str):
    """单网关健康"""
    gw = manager.get(name)
    if not gw:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    await manager.ensure_ready()
    return await gw.health_check()


@router.post("/{name}/read")
async def read_gateway(name: str, req: ReadRequest):
    """读取网关数据点"""
    await manager.ensure_ready()
    try:
        points = await manager.read(name, req.address, req.count)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    return {
        "gateway": name,
        "address": req.address,
        "count": len(points),
        "points": [
            {"tag": p.tag, "value": p.value, "timestamp": p.timestamp, "quality": p.quality}
            for p in points
        ],
    }
