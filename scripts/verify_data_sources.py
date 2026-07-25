"""数据接入层（P1）+ 多租户/图谱闭环（P2）端到端验证

不触发 lifespan（ASGITransport 直打 app）。8 步全过即证明：
1) 数据源 API 注册/列出/删除
2) agent 工具 seed→live 切换（断链修复）
3) 图谱实时闭环（live 数据 upsert）
4) 时序库内存缓冲读写
5) 注册表多租户隔离与回退

运行：python scripts/verify_data_sources.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime.data_sources import registry, DataSourceKind
from src.runtime.data_sources.base import DataSource
from src.runtime.data_sources.timeseries.tsdb import TimeSeriesDB


class FakeWMS(DataSource):
    kind = DataSourceKind.WMS

    async def is_available(self):
        return True

    async def get_inventory(self, codes=None):
        return {"IC-001": {"on_hand": 777, "reserved": 0, "warehouse": "LIVE"}}


class FakeMES(DataSource):
    kind = DataSourceKind.MES

    async def is_available(self):
        return True

    async def get_work_orders(self, status=None):
        return [{"id": "WO-9", "status": "running", "product": "P9", "qty": 50}]


async def main():
    from httpx import ASGITransport, AsyncClient

    from src.runtime.main import app
    from src.agents.supply_chain.tools import SupplyChainTools
    from src.common import neo4j_client as neo
    from src.runtime import knowledge_graph as kg

    steps = []

    # 1) API 注册内存时序库
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/data-sources", json={"kind": "timeseries", "config": {"backend": "memory"}})
        assert r.status_code == 200, r.text
        steps.append("API 注册 timeseries OK")

        # 2) API 列出含 timeseries
        r = await c.get("/data-sources")
        assert "timeseries" in {d["kind"] for d in r.json()}
        steps.append("API 列出数据源 OK")

        # 3) agent 工具 live 切换（断链修复）
        registry.register(FakeWMS(tenant_id="default"))
        tools = SupplyChainTools()
        inv = await tools.get_inventory(["IC-001"])
        assert inv["IC-001"]["warehouse"] == "LIVE"
        steps.append("供应链工具 seed→live 切换 OK")

        # 4) 图谱实时闭环
        await neo.clear_graph()
        registry.register(FakeMES(tenant_id="default"))
        stats = await kg.sync_from_sources("default")
        assert stats["merged"] >= 2
        node = await neo.get_node("MAT:IC-001")
        assert node and node["props"].get("stock_on_hand") == 777
        assert await neo.get_node("WO:WO-9") is not None
        steps.append(f"图谱实时闭环 upsert OK (merged={stats['merged']})")

        # 5) 时序库内存缓冲
        ts = TimeSeriesDB(backend="memory", tenant_id="default")
        await ts.write_metric("oee", tags={"line": "L1"}, fields={"oee": 0.9})
        pts = await ts.query_range("oee")
        assert len(pts) == 1 and pts[0]["fields"]["oee"] == 0.9
        steps.append("时序库内存缓冲读写 OK")

        # 6) 多租户隔离与回退
        from src.runtime.data_sources.connectors.domain import MESConnector
        registry.register(MESConnector(base_url="http://mes.a", tenant_id="tenantA"))
        registry.register(MESConnector(base_url="http://mes.default", tenant_id="default"))
        assert registry.get(DataSourceKind.MES, "tenantA").tenant_id == "tenantA"
        assert registry.get(DataSourceKind.MES, "ghost").tenant_id == "default"
        steps.append("注册表多租户隔离/回退 OK")

        # 7) API 删除
        r = await c.delete("/data-sources/timeseries")
        assert r.status_code == 200
        r = await c.get("/data-sources")
        assert "timeseries" not in {d["kind"] for d in r.json()}
        steps.append("API 删除 timeseries OK")

    for i, s in enumerate(steps, 1):
        print(f"  {i}. ✅ {s}")
    print(f"\n✅ 数据接入层（P1）+ 多租户/图谱闭环（P2）端到端验证全部通过（{len(steps)} 步）")


if __name__ == "__main__":
    asyncio.run(main())
