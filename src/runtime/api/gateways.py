"""网关 API——暴露全部工业协议网关的健康与读数（V1-3，多租户版）

- GET /gateways：当前租户网关健康总览（未配置则平台共享网关）
- GET /gateways/{name}：单网关健康
- POST /gateways/{name}/read：读取网关数据点（address / count）

多租户：携带 X-Tenant-Key 且租户配置了独立网关参数时，读写作用于该租户的隔离网关；
否则作用于平台共享网关。事实锚点：仅读取真实网关状态，不改写任何业务数据。
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.gateways.manager import manager
from src.runtime.api.deps import get_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gateways", tags=["gateways"])


class ReadRequest(BaseModel):
    address: str = "*"
    count: int = 10


async def _resolve(tenant: str):
    """解析当前租户的网关管理器（共享或隔离）。"""
    gw_mgr, shared = await manager.get_for_tenant(tenant)
    if shared:
        await manager.ensure_ready()
    return gw_mgr, shared


@router.get("")
async def list_gateways(tenant: str = Depends(get_tenant)):
    """当前租户全部网关健康总览"""
    gw_mgr, shared = await _resolve(tenant)
    health = await gw_mgr.health()
    health["tenant_id"] = tenant
    health["shared"] = shared
    return health


@router.get("/{name}")
async def gateway_detail(name: str, tenant: str = Depends(get_tenant)):
    """单网关健康"""
    gw_mgr, _ = await _resolve(tenant)
    gw = gw_mgr.get(name)
    if not gw:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    return await gw.health_check()


@router.post("/{name}/read")
async def read_gateway(name: str, req: ReadRequest, tenant: str = Depends(get_tenant)):
    """读取网关数据点"""
    gw_mgr, _ = await _resolve(tenant)
    try:
        points = await gw_mgr.read(name, req.address, req.count)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    return {
        "tenant_id": tenant,
        "gateway": name,
        "address": req.address,
        "count": len(points),
        "points": [
            {"tag": p.tag, "value": p.value, "timestamp": p.timestamp, "quality": p.quality}
            for p in points
        ],
    }
