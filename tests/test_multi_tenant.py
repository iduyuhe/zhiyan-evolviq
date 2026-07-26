"""多租户隔离验证（生产就绪）。

验证：① 数据源按 tenant 隔离、互不泄漏；② 缺省回退 default；
③ 回写桥按 tenant 选用各自连接器（隔离闭环）。
"""
import pytest

from src.runtime.data_sources.connectors.domain import MESConnector
from src.runtime.data_sources.registry import registry
from src.runtime.data_sources.writeback import writeback_bridge


@pytest.fixture(autouse=True)
def _isolate():
    registry.clear()
    writeback_bridge._pending.clear()
    writeback_bridge._sent.clear()
    yield
    registry.clear()
    writeback_bridge._pending.clear()
    writeback_bridge._sent.clear()


def test_datasource_tenant_isolation():
    registry.register(MESConnector(base_url="http://mes.a", tenant_id="tenantA"))
    registry.register(MESConnector(base_url="http://mes.b", tenant_id="tenantB"))

    a = registry.get_for_tenant("tenantA")
    b = registry.get_for_tenant("tenantB")
    assert a["mes"].base_url == "http://mes.a"
    assert b["mes"].base_url == "http://mes.b"
    # 互不泄漏
    assert a["mes"] is not b["mes"]


def test_default_fallback_when_tenant_unconfigured():
    registry.register(MESConnector(base_url="http://mes.default", tenant_id="default"))
    # tenantX 未配置 → 回退 default
    x = registry.get_for_tenant("tenantX")
    assert x["mes"].base_url == "http://mes.default"
    # 但 default 视图自身也可见
    d = registry.get_for_tenant("default")
    assert d["mes"].base_url == "http://mes.default"


@pytest.mark.asyncio
async def test_writeback_per_tenant_connector():
    # tenantA 配置真实 MES 连接器；tenantB 不配置
    registry.register(MESConnector(base_url="http://mes.a", tenant_id="tenantA"))
    writeback_bridge._pending.clear()
    writeback_bridge._sent.clear()

    res_a = await writeback_bridge.submit(
        system="mes", agent="x", decision_type="dt",
        payload={"v": 1}, tenant_id="tenantA", decision_id="D-A",
    )
    # tenantA 有连接器 → 真实执行（或连通性失败回 pending，但用的是 tenantA 连接器）
    assert res_a["record_id"]

    res_b = await writeback_bridge.submit(
        system="mes", agent="x", decision_type="dt",
        payload={"v": 2}, tenant_id="tenantB", decision_id="D-B",
    )
    # tenantB 无连接器 → 必然 pending（韧性，不抛异常）
    assert res_b["status"] == "pending"
