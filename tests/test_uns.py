"""T5 UNS 五路归一单元测试

验证：
1. 五路事件同 schema 归一入总线，各 channel 可查可回溯
2. gateway 路事件经 UNS 自动路由到孪生体（twin_feed）
3. collab 源正确标注 channel + entities（设备作为一等参与者）
4. 韧性降级：twin_feed 不可达时 UNS.publish 不抛、非路由事件照常入库
"""

import pytest
from src.runtime.uns import (
    UnifiedNamespace,
    CHANNEL_GATEWAY,
    CHANNEL_SYSTEM,
    CHANNEL_HUMAN,
    CHANNEL_SOCIAL,
    CHANNEL_MEETING,
    CHANNEL_COLLAB,
)
from src.runtime.data_sources.registry import registry as ds_registry
from src.runtime.data_sources.connectors.energy_twin import EnergyTwinDataSource


@pytest.fixture
def uns_inst():
    u = UnifiedNamespace()
    ds = EnergyTwinDataSource(tenant_id="default")
    ds_registry.register(ds)
    yield u, ds


def test_five_channel_normalization(uns_inst):
    u, _ = uns_inst
    u.publish_gateway("opcua://line-3", {"energy_kwh__L1": 100.0})
    u.publish_system("erp://sap/mm", {"doc": "PO123"})
    u.publish_human("wecom://zhang", {"note": "供应商交期风险"})
    u.publish_social("email://proc", {"thread": "price"})
    u.publish_meeting("meet://strategy", {"topic": "Q3"})
    u.publish_collab("collab://community-equipment", {"msg": "液压机建议维护"}, entities=["DEV:hyd-105"])
    counts = u.channel_counts()
    assert counts[CHANNEL_GATEWAY] == 1
    assert counts[CHANNEL_SYSTEM] == 1
    assert counts[CHANNEL_HUMAN] == 1
    assert counts[CHANNEL_SOCIAL] == 1
    assert counts[CHANNEL_MEETING] == 1
    assert counts[CHANNEL_COLLAB] == 1


def test_gateway_routes_to_twin(uns_inst):
    u, ds = uns_inst
    u.publish_gateway(
        "opcua://line-3",
        {"energy_kwh__SMT-L01": 51000.0, "green_ratio__SMT-L01": 33.0},
    )
    # 结构化状态应已上行到孪生体
    assert ds.twin_state["values"].get("energy_kwh__SMT-L01") == 51000.0
    assert ds.twin_state["values"].get("green_ratio__SMT-L01") == 33.0
    # 事件可查，channel/source 正确
    evs = u.query(channel=CHANNEL_GATEWAY)
    assert evs[-1]["channel"] == CHANNEL_GATEWAY
    assert evs[-1]["source"] == "opcua://line-3"


def test_system_event_with_explicit_holon_routes(uns_inst):
    u, ds = uns_inst
    # system 路带显式 holon 标注（非 machine 前缀键），也应路由到 machine 孪生体
    u.publish_system(
        "mqtt://plc-7",
        {"energy_kwh__SMT-L02": 47000.0},
        route_holon="machine",
    )
    assert ds.twin_state["values"].get("energy_kwh__SMT-L02") == 47000.0


def test_collab_source_tagged(uns_inst):
    u, _ = uns_inst
    u.publish_collab(
        "collab://community-equipment",
        {"msg": "液压机建议维护", "suggest": "更换密封件"},
        entities=["DEV:hyd-105", "LINE:3"],
    )
    ev = u.query(channel=CHANNEL_COLLAB)[-1]
    assert ev["channel"] == CHANNEL_COLLAB
    assert "DEV:hyd-105" in ev["entities"]
    assert ev["type"] == "collab_message"
    # collab 路不应路由到孪生体（非 gateway/system）
    assert "energy_kwh__" not in ev["payload"]


def test_non_routeable_channels_not_routed(uns_inst):
    u, ds = uns_inst
    before = dict(ds.twin_state["values"])
    u.publish_human("wecom://zhang", {"note": "设备异响"})
    u.publish_social("email://x", {"thread": "供应商"})
    u.publish_meeting("meet://y", {"topic": "复盘"})
    # 三路不应写入孪生体
    assert ds.twin_state["values"] == before


def test_resilience_twin_unreachable(uns_inst, monkeypatch):
    u, _ = uns_inst
    # 破坏 registry.route_event，验证 UNS.publish 不抛（韧性降级）
    def boom(*a, **k):
        raise RuntimeError("twin feed down")

    monkeypatch.setattr(ds_registry, "route_event", boom)
    ev = u.publish_gateway("opcua://line-3", {"energy_kwh__SMT-L01": 1.0})
    assert ev.channel == CHANNEL_GATEWAY
    # 非路由事件照常入库
    u.publish_human("wecom://x", {"note": "hi"})
    assert u.channel_counts()[CHANNEL_HUMAN] == 1


def test_query_filter_and_recent(uns_inst):
    u, _ = uns_inst
    for i in range(5):
        u.publish_gateway(f"opcua://line-{i}", {"energy_kwh__L{i}": float(i)})
    assert len(u.query(channel=CHANNEL_GATEWAY)) == 5
    assert len(u.query(n=3)) == 3
    assert len(u.recent(2)) == 2
