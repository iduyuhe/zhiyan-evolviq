"""回写实执行路径测试（v29.2）——证明决策经真实 HTTP POST 闭环到业务系统，而非仅 pending。

做法：启动线程内演示审计接收端，把 MES 连接器指向它，submit 后断言 status=sent
且接收端确实收到带映射字段的记录。
"""
import pytest

from src.runtime.data_sources import demo_audit_sink as sink_mod
from src.runtime.data_sources.demo_audit_sink import start, received
from src.runtime.data_sources.connectors.domain import MESConnector
from src.runtime.data_sources.registry import registry
from src.runtime.data_sources.writeback import writeback_bridge


@pytest.fixture
def _demo():
    port = 8899
    base = f"http://127.0.0.1:{port}"
    sink_mod._received.clear()
    start(port)
    conn = MESConnector(base_url=base, api_key="demo", tenant_id="default",
                        wb_field_map={"decision_id": "DecisionNo"})
    registry.register(conn)
    writeback_bridge._pending.clear()
    writeback_bridge._sent.clear()
    yield base
    registry.unregister("mes", tenant_id="default")


@pytest.mark.asyncio
async def test_submit_executes_real_post(_demo):
    res = await writeback_bridge.submit(
        system="mes", agent="supply_chain", decision_type="supply_risk_approval",
        payload={"risk": "high", "action": "hold"}, tenant_id="default",
        decision_id="DEC-001",
    )
    assert res["status"] == "sent", res
    recs = received()
    assert len(recs) == 1
    # 字段映射已应用：decision_id -> DecisionNo
    assert recs[0]["DecisionNo"] == "DEC-001"
    assert recs[0]["agent"] == "supply_chain"


@pytest.mark.asyncio
async def test_no_connector_falls_back_to_pending(_demo):
    # erp 未注册连接器 -> 仍走 pending（韧性铁律）
    res = await writeback_bridge.submit(
        system="erp", agent="cost_analysis", decision_type="cost_conclusion",
        payload={"save": 0.1}, tenant_id="default", decision_id="DEC-002",
    )
    assert res["status"] == "pending"
    assert writeback_bridge.stats()["pending"] >= 1
