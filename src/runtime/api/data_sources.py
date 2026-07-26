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


@router.post("/{kind}/test")
async def test_data_source(kind: str, body: dict | None = None, tenant: str = "default") -> dict:
    """配置 UI 连通性验证（路线图 §4.4 铁律）：在保存前先实测能否连通。

    不落库、不改动 registry：用 build_connector 构造临时实例，调用 is_available() 探测。
    body 可带 {config: {...}} 用待保存配置先行验证；缺省则用当前已注册实例验证。
    """
    from src.runtime.data_sources.config import build_connector

    cfg = (body or {}).get("config") or {}
    src = None
    # 优先用待保存配置构造临时实例
    if cfg:
        src = build_connector(kind, cfg, tenant)
    # 否则验证已注册实例
    if src is None:
        src = registry.get(kind, tenant_id=tenant)
    if src is None:
        raise HTTPException(status_code=404, detail=f"未知或未配置的数据源类型: {kind}")
    import time
    t0 = time.monotonic()
    try:
        ok = await src.is_available()
    except Exception as e:
        return {
            "ok": False,
            "kind": kind,
            "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            "detail": f"{type(e).__name__}: {e}",
        }
    return {
        "ok": bool(ok),
        "kind": kind,
        "latency_ms": round((time.monotonic() - t0) * 1000, 2),
        "detail": "连接成功" if ok else "不可达（将回退 seed）",
    }
