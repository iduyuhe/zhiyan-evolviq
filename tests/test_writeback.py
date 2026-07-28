"""ERP/MES 回写审计桥测试（韧性：不可用进 pending，可用则 sent）"""

import pytest

from src.runtime.data_sources.connectors.domain import MESConnector
from src.runtime.data_sources.registry import registry
from src.runtime.data_sources.base import DataSourceKind


class _FakeMES(MESConnector):
    def __init__(self):
        super().__init__(base_url="http://fake-mes.local")

    async def post_audit_record(self, record: dict):
        return {"ok": True, "id": "REC-1"}


@pytest.fixture(autouse=True)
def _isolate_registry():
    # 测试前后清理 mes/erp 连接器，避免污染其他用例
    before = {}
    for kind in (DataSourceKind.MES, DataSourceKind.ERP):
        c = registry.get(kind)
        if c is not None:
            before[kind] = c
    yield
    registry.clear()
    for kind, c in before.items():
        registry.register(c)


@pytest.mark.asyncio
async def test_writeback_pending_when_connector_unavailable():
    from src.runtime.data_sources.writeback import writeback_bridge

    # 确保无 mes 连接器
    registry.unregister(DataSourceKind.MES)
    res = await writeback_bridge.submit(
        system="mes", agent="supply_chain", decision_type="x", payload={"k": 1}
    )
    assert res["status"] == "pending"
    assert res["record_id"]
    # pending() 现支持按租户过滤；该用例提交到 default 租户，按租户隔离计数
    assert len(writeback_bridge.pending("default")) == 1


@pytest.mark.asyncio
async def test_writeback_sent_with_connector():
    from src.runtime.data_sources.writeback import writeback_bridge

    registry.register(_FakeMES())
    res = await writeback_bridge.submit(
        system="mes", agent="supply_chain", decision_type="y", payload={"k": 2}
    )
    assert res["status"] == "sent"
    assert writeback_bridge.stats("default")["sent_total"] == 1


@pytest.mark.asyncio
async def test_writeback_rejects_unknown_system():
    from src.runtime.data_sources.writeback import writeback_bridge

    res = await writeback_bridge.submit(
        system="crm", agent="a", decision_type="t", payload={}
    )
    assert res["status"] == "rejected"


@pytest.mark.asyncio
async def test_writeback_pending_survives_restart_p1(tmp_path, monkeypatch):
    """P1③：pending 落 SQLite，进程重启（新实例）自动恢复，不再丢队列。"""
    from src.runtime.data_sources.writeback import WritebackBridge

    db = str(tmp_path / "wb_test.db")
    monkeypatch.setenv("ZHIYAN_WRITEBACK_DB", db)
    registry.unregister(DataSourceKind.MES)

    b1 = WritebackBridge()
    res = await b1.submit(
        system="mes", agent="supply_chain", decision_type="restart_t",
        payload={"k": "持久化"}, tenant_id="TENANT_WB",
    )
    assert res["status"] == "pending"

    # 模拟重启：全新实例从盘恢复
    b2 = WritebackBridge()
    recovered = b2.pending("TENANT_WB")
    assert len(recovered) == 1
    assert recovered[0]["decision_type"] == "restart_t"

    # 重试成功后从盘删除，再次"重启"不再恢复
    registry.register(_FakeMES())
    sent = await b2.retry_pending()
    assert sent >= 1
    b3 = WritebackBridge()
    assert len(b3.pending("TENANT_WB")) == 0


@pytest.mark.asyncio
async def test_writeback_api_endpoint():
    from src.runtime.main import app
    import httpx

    registry.unregister(DataSourceKind.MES)  # 无连接器 -> pending
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as t:
        r = await t.post(
            "/writeback",
            json={"system": "mes", "agent": "supply_chain", "decision_type": "z", "payload": {"v": 9}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        # stats 端点
        s = await t.get("/writeback/stats")
        assert s.status_code == 200
        assert "pending" in s.json()
