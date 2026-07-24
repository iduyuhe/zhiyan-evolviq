"""授权引擎——评估Agent动作能否在边界内自主执行（多租户版）

核心逻辑：
- 动作类型在 require_approval_actions 中 → 必须人工审批
- 动作类型在 auto_execute_actions 中 → 进一步检查量化约束
- 量化约束越界（价格波动/数量/置信度/日限额）→ 推送人工审批
- 全部通过 → 授权内自主执行

多租户设计：
- 每个租户持有独立的授权边界集合与日限额计数（行级隔离，按 tenant_id 区分）。
- 全局单例 `authorization` 提供 `for_tenant(tid)` 返回该租户的「作用域视图」TenantAuthScope；
  视图上的所有 CRUD/评估方法都限定在该租户内。
- 为兼容既有调用（控制台/策略器默认作用于 default 租户），`authorization` 自身也暴露
  一批不带 tenant 参数的便捷方法，等价于 `for_tenant("default")`。

对应策划方案：「Agent是数字员工，不是报警器。只在超出能力或权限时才找人类」
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.runtime.models.authorization import (
    ActionDecision,
    AuthBoundary,
    AuthBoundaryCreate,
    PlannedAction,
)
from src.runtime.models.tenant import DEFAULT_TENANT_ID

logger = logging.getLogger(__name__)


def _build_default_boundaries() -> list[AuthBoundary]:
    """构造 20 个 Agent 的默认授权边界（每次调用返回全新实例，供各租户独立持有）。"""
    defaults: list[AuthBoundary] = []

    defaults.append(AuthBoundary(
        id="ab-supply-chain-default",
        name="供应链自治默认边界",
        agent="supply_chain",
        allowed_categories=["硅片", "光刻胶", "靶材", "特气", "PCB", "被动元件", "连接器"],
        price_tolerance_pct=5.0,
        max_lock_qty=50,
        confidence_threshold=0.8,
        auto_execute_actions=["lock_inventory", "notify", "adjust_priority"],
        require_approval_actions=["purchase_order", "price_change", "new_supplier"],
        max_daily_autonomous=20,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-pm-default",
        name="设备维护默认边界",
        agent="pm_maintenance",
        allowed_categories=["光刻机", "刻蚀机", "沉积设备", "贴片机", "回流焊"],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.85,
        auto_execute_actions=["notify", "adjust_priority"],
        require_approval_actions=["dispatch_repair", "order_spare", "shutdown"],
        max_daily_autonomous=10,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-quality-trace-default",
        name="质量追溯默认边界",
        agent="quality_trace",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.85,
        auto_execute_actions=["notify"],
        require_approval_actions=["create_capa"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-ipc-default",
        name="IPC标准默认边界",
        agent="ipc_standard",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.85,
        auto_execute_actions=[],
        require_approval_actions=["create_training_task"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-oee-default",
        name="OEE优化默认边界",
        agent="oee_optimizer",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.80,
        auto_execute_actions=["create_improvement_task"],
        require_approval_actions=[],
        max_daily_autonomous=20,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-smt-default",
        name="SMT换线默认边界",
        agent="smt_changeover",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.80,
        auto_execute_actions=["create_changeover_plan"],
        require_approval_actions=[],
        max_daily_autonomous=20,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-aoi-default",
        name="AOI判定默认边界",
        agent="aoi_judge",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.80,
        auto_execute_actions=["optimize_aoi_threshold"],
        require_approval_actions=[],
        max_daily_autonomous=20,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-dfm-default",
        name="DFM检查默认边界",
        agent="dfm_check",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.85,
        auto_execute_actions=["create_dfm_report"],
        require_approval_actions=["open_design_review"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-bom-default",
        name="BOM选型默认边界",
        agent="bom_selector",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.85,
        auto_execute_actions=[],
        require_approval_actions=["submit_alt_approval"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-eco-default",
        name="ECO变更默认边界",
        agent="eco_change",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.85,
        auto_execute_actions=[],
        require_approval_actions=["create_eco_task", "dispatch_eco_notice"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-yield-default",
        name="良率分析默认边界",
        agent="yield_analysis",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.80,
        auto_execute_actions=["create_doe_experiment"],
        require_approval_actions=[],
        max_daily_autonomous=15,
        enabled=True,
    ))
    # 经营决策大脑（P1 企业级）
    defaults.append(AuthBoundary(
        id="ab-aps-default",
        name="计划排程默认边界",
        agent="aps_scheduler",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.80,
        auto_execute_actions=["rebalance_schedule"],
        require_approval_actions=["expedite_order"],
        max_daily_autonomous=20,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-energy-default",
        name="能源碳ESG默认边界",
        agent="energy_carbon",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.82,
        auto_execute_actions=["create_saving_task"],
        require_approval_actions=[],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-cost-default",
        name="制造成本默认边界",
        agent="cost_analysis",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.82,
        auto_execute_actions=["create_cost_reduction"],
        require_approval_actions=[],
        max_daily_autonomous=15,
        enabled=True,
    ))
    # 经营决策大脑（P2 企业级）
    defaults.append(AuthBoundary(
        id="ab-demand-default",
        name="需求订单默认边界",
        agent="demand_order",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.80,
        auto_execute_actions=["reallocate_supply"],
        require_approval_actions=["expedite_order"],
        max_daily_autonomous=20,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-wms-default",
        name="仓储物流默认边界",
        agent="wms_logistics",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.82,
        auto_execute_actions=["create_replenishment"],
        require_approval_actions=["reroute_shipment"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    # 经营决策大脑（P3 企业级）
    defaults.append(AuthBoundary(
        id="ab-compliance-default",
        name="质量合规默认边界",
        agent="compliance_q",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.82,
        auto_execute_actions=["create_capa"],
        require_approval_actions=["escalate_compliance"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-exec-default",
        name="经营驾驶舱默认边界",
        agent="executive_cockpit",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.80,
        auto_execute_actions=["create_action_item"],
        require_approval_actions=["approve_budget_adjustment"],
        max_daily_autonomous=20,
        enabled=True,
    ))
    # 经营决策大脑（P4 企业级）
    defaults.append(AuthBoundary(
        id="ab-npi-default",
        name="研发新产导入默认边界",
        agent="rd_npi",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.82,
        auto_execute_actions=["expedite_project"],
        require_approval_actions=["reprioritize_project"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    defaults.append(AuthBoundary(
        id="ab-procurement-default",
        name="采购与供应商管理默认边界",
        agent="procurement_manage",
        allowed_categories=[],
        price_tolerance_pct=0.0,
        max_lock_qty=0,
        confidence_threshold=0.82,
        auto_execute_actions=["create_supplier_review"],
        require_approval_actions=["renegotiate_contract"],
        max_daily_autonomous=15,
        enabled=True,
    ))
    return defaults


class TenantAuthScope:
    """某租户的授权边界作用域——所有操作限定在该租户内。"""

    def __init__(self, store: "MultiTenantAuthorization", tenant_id: str):
        self._store = store
        self.tenant_id = tenant_id

    @property
    def _boundaries(self) -> dict[str, AuthBoundary]:
        return self._store._tenants[self.tenant_id]

    @property
    def _daily(self) -> dict[str, int]:
        return self._store._daily[self.tenant_id]

    # ---------- CRUD ----------
    def create(self, req: AuthBoundaryCreate) -> AuthBoundary:
        bid = f"ab-{req.agent}-{int(datetime.now(timezone.utc).timestamp())}"
        boundary = AuthBoundary(id=bid, **req.model_dump())
        self._boundaries[bid] = boundary
        logger.info(f"[{self.tenant_id}] 授权边界已创建: {boundary.name} ({bid})")
        return boundary

    def get(self, boundary_id: str) -> AuthBoundary | None:
        return self._boundaries.get(boundary_id)

    def list(self) -> list[AuthBoundary]:
        return list(self._boundaries.values())

    def update(self, boundary_id: str, req: AuthBoundaryCreate) -> AuthBoundary | None:
        if boundary_id not in self._boundaries:
            return None
        data = req.model_dump()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = self._boundaries[boundary_id].model_copy(update=data)
        self._boundaries[boundary_id] = updated
        return updated

    def patch(self, boundary_id: str, **fields) -> AuthBoundary | None:
        """局部更新单个字段（控制台「策略调整」用）。仅接受模型已有字段。"""
        cur = self._boundaries.get(boundary_id)
        if not cur:
            return None
        allowed = {k: v for k, v in fields.items() if v is not None and k in AuthBoundary.model_fields}
        if not allowed:
            return cur
        allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = cur.model_copy(update=allowed)
        self._boundaries[boundary_id] = updated
        return updated

    def delete(self, boundary_id: str) -> bool:
        return self._boundaries.pop(boundary_id, None) is not None

    def get_for_agent(self, agent: str) -> AuthBoundary | None:
        """取某Agent当前启用的边界（取第一个匹配的）"""
        for b in self._boundaries.values():
            if b.agent == agent and b.enabled:
                return b
        return None

    # ---------- 决策 ----------
    def evaluate(self, boundary: AuthBoundary, action: PlannedAction) -> ActionDecision:
        reasons: list[str] = []

        if action.type in boundary.require_approval_actions:
            return ActionDecision(
                action=action,
                decision="human",
                reason=f"动作类型『{action.type}』属于必须人工审批类",
                boundary_id=boundary.id,
            )

        if action.type not in boundary.auto_execute_actions:
            return ActionDecision(
                action=action,
                decision="human",
                reason=f"动作类型『{action.type}』未授权自主执行",
                boundary_id=boundary.id,
            )

        if boundary.allowed_categories and action.category and action.category not in boundary.allowed_categories:
            reasons.append(f"品类『{action.category}』不在白名单")

        if abs(action.price_delta_pct) > boundary.price_tolerance_pct:
            reasons.append(
                f"价格波动{action.price_delta_pct:+.1f}% 超容忍度±{boundary.price_tolerance_pct}%"
            )

        if action.qty > boundary.max_lock_qty:
            reasons.append(f"数量{action.qty} 超单次上限{boundary.max_lock_qty}")

        if action.confidence < boundary.confidence_threshold:
            reasons.append(f"置信度{action.confidence:.0%} 低于阈值{boundary.confidence_threshold:.0%}")

        today_count = self._daily.get(boundary.id, 0)
        if today_count >= boundary.max_daily_autonomous:
            reasons.append(f"已达每日自主上限{boundary.max_daily_autonomous}次")

        if reasons:
            return ActionDecision(
                action=action,
                decision="human",
                reason="；".join(reasons),
                boundary_id=boundary.id,
            )

        self._daily[boundary.id] = today_count + 1
        return ActionDecision(
            action=action,
            decision="auto",
            reason="在授权边界内，Agent可自主执行",
            boundary_id=boundary.id,
        )

    def evaluate_batch(self, boundary: AuthBoundary, actions: list[PlannedAction]) -> list[ActionDecision]:
        return [self.evaluate(boundary, a) for a in actions]


class MultiTenantAuthorization:
    """多租户授权引擎——按租户持有独立边界集合与日限额。"""

    def __init__(self):
        self._tenants: dict[str, dict[str, AuthBoundary]] = {}
        self._daily: dict[str, dict[str, int]] = {}
        self._seed(DEFAULT_TENANT_ID)

    def _seed(self, tenant_id: str) -> None:
        if tenant_id in self._tenants:
            return
        self._tenants[tenant_id] = {b.id: b for b in _build_default_boundaries()}
        self._daily[tenant_id] = {}

    def for_tenant(self, tenant_id: str) -> TenantAuthScope:
        """返回某租户的授权作用域（按需懒种子）。"""
        self._seed(tenant_id)
        return TenantAuthScope(self, tenant_id)

    # ---------- 默认租户便捷方法（兼容既有调用） ----------
    def create(self, req: AuthBoundaryCreate) -> AuthBoundary:
        return self.for_tenant(DEFAULT_TENANT_ID).create(req)

    def get(self, boundary_id: str) -> AuthBoundary | None:
        return self.for_tenant(DEFAULT_TENANT_ID).get(boundary_id)

    def list(self) -> list[AuthBoundary]:
        return self.for_tenant(DEFAULT_TENANT_ID).list()

    def update(self, boundary_id: str, req: AuthBoundaryCreate) -> AuthBoundary | None:
        return self.for_tenant(DEFAULT_TENANT_ID).update(boundary_id, req)

    def patch(self, boundary_id: str, **fields) -> AuthBoundary | None:
        return self.for_tenant(DEFAULT_TENANT_ID).patch(boundary_id, **fields)

    def delete(self, boundary_id: str) -> bool:
        return self.for_tenant(DEFAULT_TENANT_ID).delete(boundary_id)

    def get_for_agent(self, agent: str) -> AuthBoundary | None:
        return self.for_tenant(DEFAULT_TENANT_ID).get_for_agent(agent)


# 全局单例
authorization = MultiTenantAuthorization()
