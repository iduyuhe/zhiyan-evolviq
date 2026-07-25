"""数据源管理 API（P2-2 多租户配置）

- GET  /data-sources?tenant=   列出某租户已注册数据源（含可用性）
- POST /data-sources?tenant=   注入一个数据源（MES/ERP/PLM/WMS/timeseries），可选持久化
- DELETE /data-sources/{kind}?tenant=  移除某租户数据源

安全：仅配置连接参数，不触发任何自动数据改写；连接器本身韧性降级。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.runtime.data_sources import registry
from src.runtime.data_sources.config import register_from_config
from src.runtime.persistence import (
    save_tenant_data_source,
    delete_tenant_data_source,
)

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


class DataSourceConfigIn(BaseModel):
    kind: str  # mes / erp / plm / wms / timeseries
    config: dict  # {"base_url":..., "api_key":...} 或 {"backend":..., "url":...}
    name: str = ""
    persist: bool = True  # 是否落库（重启可回灌）


@router.get("")
async def list_data_sources(tenant: str = "default") -> list[dict]:
    """列出某租户已注册数据源及其可用性。"""
    sources = registry.get_for_tenant(tenant)
    out = []
    for s in sources.values():
        try:
            avail = await s.is_available()
        except Exception:
            avail = False
        out.append({
            "kind": s.kind.value,
            "name": s.name,
            "tenant": s.tenant_id,
            "available": avail,
        })
    return out


@router.post("")
async def add_data_source(body: DataSourceConfigIn, tenant: str = "default") -> dict:
    """注入一个数据源（内存注册；persist=True 时落库，重启回灌）。"""
    src = register_from_config(tenant, body.kind, body.config)
    if src is None:
        raise HTTPException(status_code=400, detail=f"未知数据源类型: {body.kind}")
    if body.persist:
        await save_tenant_data_source(tenant, body.kind, body.config, name=body.name)
    return {"status": "registered", "kind": body.kind, "tenant": tenant}


@router.delete("/{kind}")
async def remove_data_source(kind: str, tenant: str = "default") -> dict:
    """移除某租户数据源（同时移出 registry 与库）。"""
    ok = await delete_tenant_data_source(tenant, kind)
    return {"status": "removed" if ok else "not_found", "kind": kind, "tenant": tenant}
