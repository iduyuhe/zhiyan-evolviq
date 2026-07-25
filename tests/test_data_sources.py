"""数据接入层（P1）与多租户/图谱闭环（P2）测试

覆盖：
- 连接器韧性降级（未配置/不可达 → 安全空值，不抛）
- DataSourceRegistry 多租户隔离与回退
- 时序库内存环形缓冲读写
- agent 工具 seed→live 切换（断链修复）
- 图谱实时闭环 sync_from_sources（live 数据 upsert）
- 数据源 API CRUD（注册/列出/删除）
"""

import asyncio
import os
import sys

import pytest

# 确保 src 在 path（脚本从 tests/ 运行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime.data_sources import registry, DataSourceKind
from src.runtime.data_sources.base import DataSource
from src.runtime.data_sources.connectors.domain import MESConnector, WMSConnector
from src.runtime.data_sources.timeseries.tsdb import TimeSeriesDB


@pytest.fixture(autouse=True)
def _reset_registry():
    registry.clear()
    yield
    registry.clear()


# ---- 1. 连接器韧性降级 ----
async def test_mes_unconfigured_unavailable():
    m = MESConnector()
    assert await m.is_available() is False
    assert await m.get_work_orders() == []  # 空，不抛


async def test_mes_unreachable_degrades_to_empty():
    # 指向必然拒绝的地址，调用应韧性降级为空（不抛、不阻塞）
    m = MESConnector(base_url="http://127.0.0.1:1", api_key="x")
    assert await m.is_available() is True  # 配置存在
    orders = await m.get_work_orders()
    assert orders == []  # 网络失败 → 空


async def test_wms_live_returns_data(monkeypatch):
    class FakeWMS(DataSource):
        kind = DataSourceKind.WMS

        async def is_available(self):
            return True

        async def get_inventory(self, codes=None):
            return {"RES-001": {"on_hand": 99, "reserved": 1}}

    wms = FakeWMS(tenant_id="default")
    registry.register(wms)
    src = registry.get(DataSourceKind.WMS)
    assert src is wms
    assert await src.get_inventory(["RES-001"]) == {"RES-001": {"on_hand": 99, "reserved": 1}}


# ---- 2. 注册表多租户 ----
async def test_registry_multitenant_isolation_and_fallback():
    mes_default = MESConnector(base_url="http://mes.default", tenant_id="default")
    mes_a = MESConnector(base_url="http://mes.a", tenant_id="tenantA")
    registry.register(mes_default)
    registry.register(mes_a)

    # tenantA 取到自己的
    assert registry.get(DataSourceKind.MES, "tenantA") is mes_a
    # 未知租户回退 default
    assert registry.get(DataSourceKind.MES, "ghost") is mes_default
    # 未注册类型返回 None
    assert registry.get(DataSourceKind.ERP, "default") is None


# ---- 3. 时序库内存缓冲 ----
async def test_tsdb_memory_ring_buffer():
    ts = TimeSeriesDB(backend="memory", tenant_id="default")
    await ts.write_metric("oee", tags={"line": "L1"}, fields={"oee": 0.8})
    await ts.write_metric("oee", tags={"line": "L1"}, fields={"oee": 0.85})
    pts = await ts.query_range("oee")
    assert len(pts) == 2
    recent = await ts.fetch_recent("oee", limit=1)
    assert recent[-1]["fields"]["oee"] == 0.85
    assert await ts.is_available() is True


# ---- 4. agent 工具 seed→live 切换（断链修复）----
async def test_supply_chain_tool_prefers_live_wms(monkeypatch):
    from src.agents.supply_chain.tools import SupplyChainTools

    class FakeWMS(DataSource):
        kind = DataSourceKind.WMS

        async def is_available(self):
            return True

        async def get_inventory(self, codes=None):
            return {"IC-001": {"on_hand": 12345, "reserved": 0, "warehouse": "LIVE"}}

    registry.register(FakeWMS(tenant_id="default"))
    tools = SupplyChainTools()
    inv = await tools.get_inventory(["IC-001"])
    assert inv["IC-001"]["warehouse"] == "LIVE"  # live 命中


async def test_supply_chain_tool_falls_back_to_seed_when_no_source():
    from src.agents.supply_chain.tools import SupplyChainTools

    tools = SupplyChainTools()
    inv = await tools.get_inventory(["CAP-001"])
    # 无 live 源 → 回退 seed（不应是 live 标记的 "LIVE" 仓库）
    assert "CAP-001" in inv
    assert inv["CAP-001"].get("warehouse") != "LIVE"


# ---- 5. 图谱实时闭环 ----
async def test_graph_sync_from_sources_ingests_live():
    from src.common import neo4j_client as neo
    from src.runtime import knowledge_graph as kg

    await neo.clear_graph()

    class FakeWMS(DataSource):
        kind = DataSourceKind.WMS

        async def is_available(self):
            return True

        async def get_inventory(self, codes=None):
            return {"MAT-X": {"on_hand": 50, "reserved": 5}}

    class FakeMES(DataSource):
        kind = DataSourceKind.MES

        async def is_available(self):
            return True

        async def get_work_orders(self, status=None):
            return [{"id": "WO-1", "status": "running", "product": "P1", "qty": 100}]

    registry.register(FakeWMS(tenant_id="default"))
    registry.register(FakeMES(tenant_id="default"))

    stats = await kg.sync_from_sources("default")
    assert stats["merged"] >= 2
    # Material 库存属性被 live 更新
    node = await neo.get_node("MAT:MAT-X")
    assert node is not None
    assert node["props"].get("stock_on_hand") == 50
    # WorkOrder 节点被创建
    wo = await neo.get_node("WO:WO-1")
    assert wo is not None


# ---- 6. 数据源 API CRUD ----
async def test_data_sources_api_crud():
    from httpx import ASGITransport, AsyncClient

    from src.runtime.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 注册一个内存时序库
        r = await c.post("/data-sources", json={"kind": "timeseries", "config": {"backend": "memory"}})
        assert r.status_code == 200, r.text
        # 列出应包含 timeseries
        r = await c.get("/data-sources")
        assert r.status_code == 200
        kinds = {d["kind"] for d in r.json()}
        assert "timeseries" in kinds
        # 删除
        r = await c.delete("/data-sources/timeseries")
        assert r.status_code == 200
        r = await c.get("/data-sources")
        kinds = {d["kind"] for d in r.json()}
        assert "timeseries" not in kinds
