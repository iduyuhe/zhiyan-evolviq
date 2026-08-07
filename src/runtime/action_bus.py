"""统一执行总线 + 人机协同闸门（刀2 迭代1）。

把分散的"手 / 脚"能力（联邦工具注册表 + 后续 UNS / 文档 / API / 浏览器通道）组织为统一的
ActionBus，并为人机协同闸门（human-in-the-loop）定义标准接口
confirm / authorize / rollback / receipt。不可逆动作（ERP/MES 回写等）先行上闸。

设计纪律（范围基线 docs/TECHNICAL_DELIVERY_SCOPE.md §3/§6）：
- 零真名：action 元信息只含工具名 / agent / 描述，不含案例真名。
- 挖存量：本迭代复用既有 TOOL_REGISTRY，不改写既有工具实现；闸门接 writeback 留待迭代2。
- 延迟部署：纯后端结构化，未接入运行时 import（_default_* 懒加载），符合基线 §4。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# 通道分类（刀2 DoD：覆盖回写 / UNS / 文档 / API / 浏览器）
CHANNELS = ("agent_tool", "writeback", "uns", "document", "api", "browser")

# 不可逆动作（ERP/MES 回写 / 对外任务生成）先行上闸：显式命名 + 关键字规则
_IRREVERSIBLE_EXACT = {
    "supply_chain__lock_inventory",
    "bom_selector__submit_alt_approval",
    "wms_logistics__create_replenishment",
    "aps_scheduler__rebalance_schedule",
    "demand_order__reallocate_supply",
}
_IRREVERSIBLE_KEYWORDS = ("lock_", "submit_", "rebalance_", "reallocate_", "create_replenishment")


def classify_require_gate(name: str) -> bool:
    """判断动作是否不可逆、需人机协同闸门授权。"""
    if name in _IRREVERSIBLE_EXACT:
        return True
    return any(k in name for k in _IRREVERSIBLE_KEYWORDS)


def classify_channel(name: str) -> str:
    """通道归类：不可逆动作归 writeback（需闸门），其余归 agent_tool。"""
    if classify_require_gate(name):
        return "writeback"
    return "agent_tool"


@dataclass
class ActionSpec:
    name: str
    agent: str
    description: str
    params: Dict[str, Any]
    channel: str = "agent_tool"
    require_gate: bool = False
    gate_reason: str = ""

    @classmethod
    def from_registry(cls, name: str, spec) -> "ActionSpec":
        agent, _method, desc, params = spec
        gate = classify_require_gate(name)
        return cls(
            name=name, agent=agent, description=desc, params=params or {},
            channel=classify_channel(name),
            require_gate=gate,
            gate_reason=("不可逆动作：ERP/MES 回写 / 对外任务生成，需人工授权"
                         if gate else ""),
        )


@dataclass
class Receipt:
    receipt_id: str
    action_name: str
    status: str            # pending / authorized / executed / rolled_back / rejected
    require_gate: bool
    issued_at: float
    actor: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "action_name": self.action_name,
            "status": self.status,
            "require_gate": self.require_gate,
            "issued_at": self.issued_at,
            "actor": self.actor,
            "detail": self.detail,
        }


class GateError(Exception):
    pass


class ActionGate:
    """人机协同闸门标准接口：confirm / authorize / rollback / receipt。

    迭代1：内存实现（pending 状态机 + receipt 记录）。迭代2 将 authorize 接 writeback
    审计三合一（pending 落盘可恢复）；rollback 接写回撤销。
    """

    def __init__(self) -> None:
        self._receipts: Dict[str, Receipt] = {}

    def request_confirmation(self, spec: ActionSpec, args: Dict[str, Any],
                             actor: str) -> Receipt:
        rid = uuid.uuid4().hex[:12]
        r = Receipt(
            receipt_id=rid, action_name=spec.name, status="pending",
            require_gate=spec.require_gate, issued_at=time.time(), actor=actor,
            detail={"args": args, "channel": spec.channel,
                    "gate_reason": spec.gate_reason},
        )
        self._receipts[rid] = r
        return r

    def get_receipt(self, receipt_id: str) -> Receipt:
        r = self._receipts.get(receipt_id)
        if not r:
            raise GateError(f"未知 receipt: {receipt_id}")
        return r

    def authorize(self, receipt_id: str, actor: str) -> Receipt:
        r = self.get_receipt(receipt_id)
        if r.status != "pending":
            raise GateError(f"receipt {receipt_id} 状态 {r.status} 不可授权")
        r.status = "authorized"
        r.actor = actor
        return r

    def rollback(self, receipt_id: str, actor: str) -> Receipt:
        r = self.get_receipt(receipt_id)
        if r.status in ("executed", "rolled_back"):
            raise GateError(f"receipt {receipt_id} 已 {r.status}，无法回滚")
        r.status = "rolled_back"
        r.actor = actor
        return r

    def mark_executed(self, receipt_id: str, result: Dict[str, Any]) -> Receipt:
        r = self.get_receipt(receipt_id)
        r.status = "executed"
        r.detail = {**r.detail, "result": result}
        return r


def _default_registry() -> Dict[str, Any]:
    """懒加载既有联邦工具注册表（挖存量，不改写其实现）。"""
    try:
        from src.runtime.mcp.federation import TOOL_REGISTRY
        return TOOL_REGISTRY
    except Exception:
        return {}


async def _default_dispatch(tool_name: str, args: Dict[str, Any],
                            tenant_id: str) -> Dict[str, Any]:
    from src.runtime.mcp.federation import dispatch
    return await dispatch(tool_name, args, tenant_id)


async def _default_writeback_submit(system: str, agent: str, decision_type: str,
                                    payload: Dict[str, Any], tenant_id: str,
                                    decision_id: str | None = None) -> Dict[str, Any]:
    """默认回写审计提交（审计三合一：连接器不可达自动进 pending 落盘可恢复）。"""
    from src.runtime.data_sources.writeback import writeback_bridge
    return await writeback_bridge.submit(
        system, agent, decision_type, payload, tenant_id, decision_id)


def _default_writeback_cancel(record_id: str, tenant_id: str) -> Dict[str, Any]:
    """默认回写审计取消（人工回滚，sent 前可撤回）。"""
    from src.runtime.data_sources.writeback import writeback_bridge
    return writeback_bridge.cancel_pending(record_id, tenant_id)


class ActionBus:
    """统一执行总线：把工具注册表组织为可治理的动作，并接人机协同闸门。"""

    def __init__(self, registry: Optional[Dict[str, Any]] = None,
                 dispatch_fn: Optional[Callable] = None,
                 gate: Optional[ActionGate] = None,
                 writeback_submit: Optional[Callable] = None,
                 writeback_cancel: Optional[Callable] = None) -> None:
        self._registry = registry if registry is not None else _default_registry()
        self._dispatch = dispatch_fn or _default_dispatch
        self._gate = gate or ActionGate()
        self._wb_submit = writeback_submit or _default_writeback_submit
        self._wb_cancel = writeback_cancel or _default_writeback_cancel
        self._specs: Dict[str, ActionSpec] = {}
        for name, spec in self._registry.items():
            self._specs[name] = ActionSpec.from_registry(name, spec)

    def list_actions(self) -> List[ActionSpec]:
        return list(self._specs.values())

    def list_gated(self) -> List[ActionSpec]:
        return [s for s in self._specs.values() if s.require_gate]

    def get_spec(self, name: str) -> ActionSpec:
        s = self._specs.get(name)
        if not s:
            raise GateError(f"未知 action: {name}")
        return s

    async def execute(self, name: str, args: Dict[str, Any] | None = None,
                      actor: str = "system", tenant_id: str = "default") -> Receipt:
        spec = self.get_spec(name)
        args = args or {}
        if not spec.require_gate:
            result = await self._dispatch(name, args, tenant_id)
            return Receipt(
                receipt_id=uuid.uuid4().hex[:12], action_name=name, status="executed",
                require_gate=False, issued_at=time.time(), actor=actor,
                detail={"args": args, "result": result},
            )
        # 需闸门：先留 pending receipt，并同步提交回写审计桥（未过账前可回滚）；
        # 状态保持 pending 等人工 authorize 后才真正 dispatch。
        r = self._gate.request_confirmation(spec, args, actor)
        wb = await self._wb_submit(
            system="erp", agent=spec.agent, decision_type=spec.name,
            payload={"args": args, "receipt_id": r.receipt_id,
                      "gate_reason": spec.gate_reason},
            tenant_id=tenant_id, decision_id=r.receipt_id,
        )
        r.detail = {**r.detail, "writeback": wb}
        return r

    async def authorize(self, receipt_id: str, actor: str = "human",
                        tenant_id: str = "default") -> Receipt:
        r = self._gate.authorize(receipt_id, actor)
        args = r.detail.get("args", {})
        action_name = r.action_name
        # 认证后真正执行不可逆动作（经由底层 dispatch，审计三合一桥已留痕）
        result = await self._dispatch(action_name, args, tenant_id)
        return self._gate.mark_executed(receipt_id, result)

    def rollback(self, receipt_id: str, actor: str = "human",
                 tenant_id: str = "default") -> Receipt:
        r = self._gate.rollback(receipt_id, actor)
        # 回滚：取消尚未过账的回写审计记录（已 sent 则不可撤，符合智衍不篡账本）
        wb_record_id = (r.detail.get("writeback") or {}).get("record_id")
        if wb_record_id:
            wb = self._wb_cancel(wb_record_id, tenant_id)
            r.detail = {**r.detail, "writeback_rollback": wb}
        return r

    def get_receipt(self, receipt_id: str) -> Receipt:
        return self._gate.get_receipt(receipt_id)


# ---------------------------------------------------------------------------
# MCP-native 互操作 + Skill 边界（HubPort 启发 · 挖存量，纯附加）
# ---------------------------------------------------------------------------
# 设计纪律（docs/EXTERNAL_NARRATIVE §16 一致）：
# - 运行时确定性：ActionSpec 的契约（name/agent/params/channel/gate）一经注册固定，
#   不随 AI 生成漂移；MCP 暴露层只做「协议映射」，不改写动作语义。
# - Skill 边界：Agent ≠ 技能。对外讲"分身能做什么技能"，本映射层把 ActionSpec
#   归并到「角色分身 × 技能」视图，权限是技能的副产品（L0–L3）。
# - 绝不引入运行时 MCP 传输依赖到 Agent 内部（与 federation.py 一致，零韧性风险）。

def to_mcp_tool_spec(spec: "ActionSpec") -> Dict[str, Any]:
    """把内部 ActionSpec 映射为 MCP-native tool 描述（外部暴露层用）。

    字段对齐 MCP tool 对象：name / description / inputSchema / annotations。
    不含任何案例真名（零真名铁律）。
    """
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": {
            "type": "object",
            "properties": spec.params or {},
            "additionalProperties": False,
        },
        "annotations": {
            "channel": spec.channel,
            "require_gate": spec.require_gate,
            "read_only_hint": not spec.require_gate,
            "destructive_hint": spec.require_gate,
        },
    }


def to_skill_view(specs: List["ActionSpec"]) -> Dict[str, Any]:
    """把动作归并到「角色分身 × 技能」视图（Skill 边界映射层）。

    返回：
        {
          "roles": { agent: { "display": ..., "skills": [skill_name...] } },
          "gated_skills": [...],   # 需人工授权的技能（不可逆）
        }
    说明：agent 内部名 → 对外「分身」展示名在 EXTERNAL_NARRATIVE §2 四层框架定义，
    此处只做聚合，不擅自命名。
    """
    roles: Dict[str, Dict[str, Any]] = {}
    gated: List[str] = []
    for s in specs:
        entry = roles.setdefault(s.agent, {"agent": s.agent, "skills": []})
        entry["skills"].append(s.name)
        if s.require_gate:
            gated.append(s.name)
    return {"roles": roles, "gated_skills": gated}
