"""授权边界数据模型——AI原生核心

定义人类赋予Agent的"行动许可证"：Agent只能在边界内自主执行，
超出边界的动作必须推送给人审批。这是人从"监工"变"老板"的契约基础。

对应策划方案 模块四「企业控制台」→ 授权边界配置 (MVP必修)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class AuthBoundary(BaseModel):
    """授权边界配置

    Attributes:
        agent: 适用的Agent ID（如 supply_chain / pm_maintenance）
        allowed_categories: 允许自主操作的物料/对象品类白名单
        price_tolerance_pct: 价格波动容忍度（%）——超出需审批
        max_lock_qty: 单次最大锁定数量——超出需审批
        confidence_threshold: 置信度阈值（0-1）——低于则推送人确认
        auto_execute_actions: 可授权内自主执行的动作类型
        require_approval_actions: 必须人工审批的动作类型
        max_daily_autonomous: 每日最大自主执行次数（防失控）
    """

    id: str
    name: str
    agent: str
    allowed_categories: list[str] = Field(default_factory=list)
    price_tolerance_pct: float = 5.0
    max_lock_qty: int = 50
    confidence_threshold: float = 0.8
    auto_execute_actions: list[str] = Field(default_factory=lambda: ["lock_inventory", "notify", "adjust_priority"])
    require_approval_actions: list[str] = Field(default_factory=lambda: ["purchase_order", "price_change", "new_supplier"])
    max_daily_autonomous: int = 20
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuthBoundaryCreate(BaseModel):
    """创建授权边界的请求体"""

    name: str
    agent: str
    allowed_categories: list[str] = Field(default_factory=list)
    price_tolerance_pct: float = 5.0
    max_lock_qty: int = 50
    confidence_threshold: float = 0.8
    auto_execute_actions: list[str] = Field(default_factory=lambda: ["lock_inventory", "notify", "adjust_priority"])
    require_approval_actions: list[str] = Field(default_factory=lambda: ["purchase_order", "price_change", "new_supplier"])
    max_daily_autonomous: int = 20
    enabled: bool = True


class PlannedAction(BaseModel):
    """Agent规划出的一个待执行动作

    引擎在execute()时构造，交由AuthorizationEngine评估。
    """

    type: str  # lock_inventory / purchase_order / price_change / notify / adjust_priority ...
    category: str = ""  # 物料品类 / 对象类型
    price_delta_pct: float = 0.0  # 相对基准的价格波动
    qty: int = 0  # 操作数量
    confidence: float = 1.0  # Agent对该动作的置信度
    detail: str = ""  # 人类可读说明
    session_id: str = ""


class ActionDecision(BaseModel):
    """单个动作的授权决策结果"""

    action: PlannedAction
    decision: str  # auto / human
    reason: str
    boundary_id: str
