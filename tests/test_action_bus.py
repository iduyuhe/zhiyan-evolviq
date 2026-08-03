"""刀2 行动层统一执行总线 · 迭代1+2 测试（复用 TOOL_REGISTRY + 人机协同闸门 + 回写审计桥）

覆盖（迭代1）：
- 不可逆动作分类（ERP/MES 回写 / 对外任务生成）require_gate=True；只读工具不闸。
- ActionBus.execute：非闸门动作立即执行（dispatch 一次）；闸门动作返回 pending 且不 dispatch。
- 标准闸门接口：authorize 后 dispatch 执行；rollback 在 authorize 前可撤回。
- 覆盖既有工具注册表（默认 TOOL_REGISTRY ≥ 60 工具，闸门集非空）。

覆盖（迭代2 · 接 writeback 审计三合一）：
- 闸门动作 execute 即提交回写审计 pending（落账本未过账前留痕），receipt 含 writeback 记录。
- authorize 后才真正 dispatch 执行（审计桥已留痕）。
- rollback 取消尚未过账的回写审计记录（已 sent 不可撤，符合智衍不篡账本）。

🔴 匿名铁律：action 元信息序列化不含 LEAK_TOKENS 真实锚定片段。
范围纪律（docs/TECHNICAL_DELIVERY_SCOPE.md）：纯后端，不接入运行时 import（懒加载），
不扩 agent / 前端 / REST 端点，符合延迟部署纪律。
"""
import json

import pytest

from src.agents.compliance_reviewer.agent import LEAK_TOKENS
from src.runtime.action_bus import (
    ActionBus, ActionGate, classify_require_gate, classify_channel,
)


class _FakeRegistry:
    """内置小注册表（name -> (agent, method, desc, params)），避免触碰真实 federation。"""
    REG = {
        "supply_chain__get_inventory": ("supply_chain", "get_inventory", "查询库存", {"material_codes": "array"}),
        "supply_chain__lock_inventory": ("supply_chain", "lock_inventory", "锁定库存", {"material_code": "string"}),
        "wms_logistics__create_replenishment": ("wms_logistics", "create_replenishment", "生成补货", {"material": "string"}),
        "bom_selector__submit_alt_approval": ("bom_selector", "submit_alt_approval", "提交替代审批", {"target": "string"}),
    }


@pytest.fixture
def bus_with_calls():
    calls = []
    wb = []
    counter = {"n": 0}

    async def fake_dispatch(name, args, tenant_id):
        calls.append((name, args, tenant_id))
        return {"ok": True, "name": name, "tenant": tenant_id}

    async def fake_wb_submit(system, agent, decision_type, payload, tenant_id, decision_id=None):
        counter["n"] += 1
        rid = f"wb_{counter['n']}"
        wb.append({"record_id": rid, "system": system, "agent": agent, "decision_type": decision_type})
        return {"status": "pending", "record_id": rid}

    def fake_wb_cancel(record_id, tenant_id):
        wb.append({"cancel": record_id})
        return {"status": "cancelled", "record_id": record_id}

    bus = ActionBus(
        registry=_FakeRegistry.REG, dispatch_fn=fake_dispatch,
        writeback_submit=fake_wb_submit, writeback_cancel=fake_wb_cancel,
    )
    return bus, calls, wb


def test_classify_require_gate():
    assert classify_require_gate("supply_chain__lock_inventory") is True
    assert classify_require_gate("wms_logistics__create_replenishment") is True
    assert classify_require_gate("bom_selector__submit_alt_approval") is True
    assert classify_require_gate("aps_scheduler__rebalance_schedule") is True
    assert classify_require_gate("supply_chain__get_inventory") is False


def test_classify_channel():
    assert classify_channel("supply_chain__lock_inventory") == "writeback"
    assert classify_channel("supply_chain__get_inventory") == "agent_tool"


async def test_non_gated_executes_immediately(bus_with_calls):
    bus, calls, wb = bus_with_calls
    r = await bus.execute("supply_chain__get_inventory", {"material_codes": ["X"]})
    assert r.status == "executed"
    assert r.require_gate is False
    assert len(calls) == 1, "非闸门动作应直接 dispatch 一次"
    assert len(wb) == 0, "只读动作不应触发回写审计"


async def test_gated_returns_pending_and_no_dispatch(bus_with_calls):
    bus, calls, wb = bus_with_calls
    r = await bus.execute("supply_chain__lock_inventory", {"material_code": "PCB-1"})
    assert r.status == "pending", "闸门动作应先留 pending"
    assert r.require_gate is True
    assert len(calls) == 0, "闸门动作在授权前不得 dispatch"
    assert len(wb) == 1, "闸门动作 execute 即提交回写审计 pending"
    assert wb[0]["decision_type"] == "supply_chain__lock_inventory"
    assert wb[0]["system"] == "erp"


async def test_gated_authorize_executes(bus_with_calls):
    bus, calls, wb = bus_with_calls
    r = await bus.execute("supply_chain__lock_inventory", {"material_code": "PCB-1"})
    rid = r.receipt_id
    r2 = await bus.authorize(rid, actor="human")
    assert r2.status == "executed"
    assert len(calls) == 1, "授权后 dispatch 一次"
    assert wb[0]["record_id"] in str(r2.detail), "receipt 应关联回写审计记录"


async def test_rollback_before_authorize(bus_with_calls):
    bus, calls, wb = bus_with_calls
    r = await bus.execute("wms_logistics__create_replenishment", {"material": "M"})
    rid = r.receipt_id
    pending_wb_id = wb[0]["record_id"]
    rb = bus.rollback(rid, actor="human")
    assert rb.status == "rolled_back"
    assert len(calls) == 0, "回滚后不得 dispatch"
    # 回滚应取消同一条 pending 回写审计记录
    assert wb[-1].get("cancel") == pending_wb_id, "回滚须取消对应回写审计记录"


async def test_list_actions_and_gated(bus_with_calls):
    bus, _c, _w = bus_with_calls
    specs = bus.list_actions()
    assert len(specs) == len(_FakeRegistry.REG)
    gated = bus.list_gated()
    assert {s.name for s in gated} == {
        "supply_chain__lock_inventory",
        "wms_logistics__create_replenishment",
        "bom_selector__submit_alt_approval",
    }


def test_covers_real_registry():
    """ActionBus 默认复用既有 TOOL_REGISTRY（挖存量，覆盖现有回写/工具）。"""
    bus = ActionBus()  # 默认加载 federation.TOOL_REGISTRY
    assert len(bus.list_actions()) >= 60, "应覆盖既有联邦工具注册表"
    assert bus.list_gated(), "应存在已识别的不可逆（闸门）动作"


def test_anon_no_leak_in_action_specs(bus_with_calls):
    bus, _c, _w = bus_with_calls
    blob = json.dumps([s.__dict__ for s in bus.list_actions()], ensure_ascii=False)
    hits = [t for t in LEAK_TOKENS if t in blob]
    assert not hits, f"❌ 动作元信息泄露真实锚定名：{hits}"
