"""授权引擎——评估Agent动作能否在边界内自主执行

核心逻辑：
- 动作类型在 require_approval_actions 中 → 必须人工审批
- 动作类型在 auto_execute_actions 中 → 进一步检查量化约束
- 量化约束越界（价格波动/数量/置信度/日限额）→ 推送人工审批
- 全部通过 → 授权内自主执行

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

logger = logging.getLogger(__name__)


class AuthorizationEngine:
    """授权边界引擎——内存存储 + 决策评估"""

    def __init__(self):
        self._boundaries: dict[str, AuthBoundary] = {}
        self._daily_autonomous_count: dict[str, int] = {}  # boundary_id -> 今日自主执行数
        self._seed_defaults()

    def _seed_defaults(self):
        """种子默认边界——供应链Agent的示例授权"""
        default = AuthBoundary(
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
        )
        self._boundaries[default.id] = default

        pm = AuthBoundary(
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
        )
        self._boundaries[pm.id] = pm

        # ---- 质量侦探 / 产线管家 / 研发加速器：8 个 Agent 默认边界 ----
        # 原则：高风险动作（变更/替代/评审/ECO/CAPA/培训）需人工审批；
        #       低风险（建报告/计划/任务）授权内自主；新 Agent 不设品类限制。
        quality_trace = AuthBoundary(
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
        )
        self._boundaries[quality_trace.id] = quality_trace

        ipc = AuthBoundary(
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
        )
        self._boundaries[ipc.id] = ipc

        oee = AuthBoundary(
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
        )
        self._boundaries[oee.id] = oee

        smt = AuthBoundary(
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
        )
        self._boundaries[smt.id] = smt

        aoi = AuthBoundary(
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
        )
        self._boundaries[aoi.id] = aoi

        dfm = AuthBoundary(
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
        )
        self._boundaries[dfm.id] = dfm

        bom = AuthBoundary(
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
        )
        self._boundaries[bom.id] = bom

        eco = AuthBoundary(
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
        )
        self._boundaries[eco.id] = eco

        yield_an = AuthBoundary(
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
        )
        self._boundaries[yield_an.id] = yield_an

    # ---------- CRUD ----------
    def create(self, req: AuthBoundaryCreate) -> AuthBoundary:
        bid = f"ab-{req.agent}-{int(datetime.now(timezone.utc).timestamp())}"
        boundary = AuthBoundary(id=bid, **req.model_dump())
        self._boundaries[bid] = boundary
        logger.info(f"授权边界已创建: {boundary.name} ({bid})")
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
        """评估单个动作是否可在授权内自主执行"""
        reasons: list[str] = []

        # 1. 动作类型硬性要求审批
        if action.type in boundary.require_approval_actions:
            return ActionDecision(
                action=action,
                decision="human",
                reason=f"动作类型『{action.type}』属于必须人工审批类",
                boundary_id=boundary.id,
            )

        # 2. 动作类型不在自主执行清单
        if action.type not in boundary.auto_execute_actions:
            return ActionDecision(
                action=action,
                decision="human",
                reason=f"动作类型『{action.type}』未授权自主执行",
                boundary_id=boundary.id,
            )

        # 3. 品类白名单
        if boundary.allowed_categories and action.category and action.category not in boundary.allowed_categories:
            reasons.append(f"品类『{action.category}』不在白名单")

        # 4. 价格波动
        if abs(action.price_delta_pct) > boundary.price_tolerance_pct:
            reasons.append(
                f"价格波动{action.price_delta_pct:+.1f}% 超容忍度±{boundary.price_tolerance_pct}%"
            )

        # 5. 锁定数量
        if action.qty > boundary.max_lock_qty:
            reasons.append(f"数量{action.qty} 超单次上限{boundary.max_lock_qty}")

        # 6. 置信度
        if action.confidence < boundary.confidence_threshold:
            reasons.append(f"置信度{action.confidence:.0%} 低于阈值{boundary.confidence_threshold:.0%}")

        # 7. 日自主执行次数
        today_count = self._daily_autonomous_count.get(boundary.id, 0)
        if today_count >= boundary.max_daily_autonomous:
            reasons.append(f"已达每日自主上限{boundary.max_daily_autonomous}次")

        if reasons:
            return ActionDecision(
                action=action,
                decision="human",
                reason="；".join(reasons),
                boundary_id=boundary.id,
            )

        # 通过：记入日限额
        self._daily_autonomous_count[boundary.id] = today_count + 1
        return ActionDecision(
            action=action,
            decision="auto",
            reason="在授权边界内，Agent可自主执行",
            boundary_id=boundary.id,
        )

    def evaluate_batch(self, boundary: AuthBoundary, actions: list[PlannedAction]) -> list[ActionDecision]:
        """批量评估"""
        return [self.evaluate(boundary, a) for a in actions]


# 全局单例
authorization = AuthorizationEngine()
