"""pytest：energy_carbon agent 消费 twin_context 实时孪生推理（阶段1下半场）

纳入零回归套件：验证「网关实时流 → 孪生体 → agent 实时结论」链路及韧性降级。
"""

import asyncio

import pytest

from src.runtime.data_sources import registry as ds_registry
from src.runtime.data_sources.connectors.energy_twin import EnergyTwinDataSource
from src.agents.energy_carbon.agent import energy_carbon_agent


@pytest.fixture(autouse=True)
def _energy_twin():
    # 幂等注册能耗孪生体（模拟 config 默认租户引导注册）
    ds_registry.register(EnergyTwinDataSource(tenant_id="default"))
    yield
    # 仅重建能耗孪生体，不扰动其他已注册源（避免影响同会话其他测试）
    ds_registry.register(EnergyTwinDataSource(tenant_id="default"))


def _reset_machine_twins():
    for src in ds_registry.get_for_tenant("default").values():
        h = getattr(src, "holon_kind", None)
        if h and h.value == "machine":
            src.twin_state = {"values": {}, "updated_at": None, "source": None}


async def _analyze(goal="分析本周能耗与碳排"):
    return await energy_carbon_agent.analyze(goal)


def test_no_twin_falls_back_to_seed():
    r = asyncio.run(_analyze())
    assert r["status"] == "completed"
    assert r["twin_context"]["enabled"] is False
    assert "无实时孪生流" in r["summary"]


def test_realtime_stream_produces_real_time_fields():
    ds_registry.route_event(
        "machine",
        {
            "energy_kwh__SMT-L01": 51000.0,
            "power_kw__SMT-L01": 320.5,
            "green_ratio__SMT-L01": 33.0,
            "energy_kwh__DIFF": 58000.0,
            "green_ratio__DIFF": 12.0,
        },
        source="opcua-sim",
    )
    r = asyncio.run(_analyze())
    tc = r["twin_context"]
    assert tc["enabled"] is True
    assert "energy_kwh" in tc["real_time_fields"]
    assert tc["lines"]["SMT-L01"]["energy_kwh"] == 51000.0
    assert tc["fresh"] is True
    smt = next(l for l in r["lines"] if l["line_id"] == "SMT-L01")
    assert smt["real_time"] is True
    assert smt["green_ratio"] == 33.0


def test_resilience_after_twin_cleared():
    ds_registry.route_event("machine", {"energy_kwh__SMT-L01": 51000.0}, source="x")
    _reset_machine_twins()  # 模拟孪生流不可用（不扰动其他数据源）
    r = asyncio.run(_analyze())
    assert r["twin_context"]["enabled"] is False
    assert r["status"] == "completed"
