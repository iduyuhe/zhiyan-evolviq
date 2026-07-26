"""配置 UI 连通性聚合 API（v29.9 · 路线图 §4.4 铁律）

- GET  /api/connectivity              聚合全子系统连通性（DB / 知识图谱 / 网关 / 数据源 / 社交连接器）
- POST /api/connectivity/gateway      单协议网关连通性测试（opcua/mqtt/modbus/ipc_cfx + endpoint）
- POST /api/connectivity/datasource   单数据源连通性测试（kind + config）

所有测试均带超时、不改动生产状态、失败静默降级，仅回显结果供 UI 红绿展示。
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel

from src.common.db import db_status
from src.runtime.data_sources import registry
from src.runtime.data_sources.config import build_connector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectivity", tags=["connectivity"])


class GatewayTestIn(BaseModel):
    protocol: str  # opcua | mqtt | modbus | ipc_cfx
    endpoint: str | None = None
    port: int | None = None


class DataSourceTestIn(BaseModel):
    kind: str  # mes | erp | plm | wms | timeseries
    config: dict = {}


@router.get("")
async def connectivity_overview() -> dict:
    out: dict = {"timestamp": time.time()}

    # 数据库
    try:
        out["db"] = db_status()
    except Exception as e:
        out["db"] = {"available": False, "error": str(e)}

    # 知识图谱
    try:
        from src.common import neo4j_client as neo
        out["knowledge_graph"] = {"available": neo.neo_available, "mode": neo.neo_mode}
    except Exception as e:
        out["knowledge_graph"] = {"error": str(e)}

    # 网关
    try:
        from src.gateways.manager import manager as gw
        await gw.ensure_ready()
        out["gateways"] = await gw.health()
    except Exception as e:
        out["gateways"] = {"error": str(e)}

    # 数据源
    try:
        ds = []
        for s in registry.list():
            try:
                avail = await s.is_available()
            except Exception:
                avail = False
            ds.append({"kind": s.kind.value, "name": s.name, "available": avail})
        out["data_sources"] = ds
    except Exception as e:
        out["data_sources"] = {"error": str(e)}

    # 社交连接器
    try:
        from src.runtime.connectors.manager import manager as cm
        out["connectors"] = cm.list()
    except Exception as e:
        out["connectors"] = {"error": str(e)}

    return out


@router.post("/gateway")
async def test_gateway(req: GatewayTestIn) -> dict:
    from src.gateways.manager import manager as gw

    await gw.ensure_ready()
    result = await gw.test_protocol(req.protocol, endpoint=req.endpoint, port=req.port)
    return {"protocol": req.protocol, **result}


@router.post("/datasource")
async def test_datasource(req: DataSourceTestIn) -> dict:
    src = build_connector(req.kind, req.config, tenant_id="default")
    if src is None:
        return {"ok": False, "kind": req.kind, "detail": f"未知或未配置的数据源类型: {req.kind}"}
    t0 = time.monotonic()
    try:
        ok = await src.is_available()
    except Exception as e:
        return {
            "ok": False,
            "kind": req.kind,
            "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            "detail": f"{type(e).__name__}: {e}",
        }
    return {
        "ok": bool(ok),
        "kind": req.kind,
        "latency_ms": round((time.monotonic() - t0) * 1000, 2),
        "detail": "连接成功" if ok else "不可达（将回退 seed）",
    }
