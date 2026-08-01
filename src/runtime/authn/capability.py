"""权限第③层——业务角色（BusinessRole）+ 功能作用域（CapabilityScope）

四层权限模型中的第③层，补齐"同一租户内不同岗位看到不同智能体"的缺口：

    ① 租户隔离      X-Tenant-Key fail-closed（跨企业不可见）
    ② 用户 RBAC     viewer/operator/tenant_admin/superadmin（能做多重的事）
    ③ 业务角色      device_engineer/quality_manager/...（能看哪些智能体）← 本模块
    ④ Agent 边界    AuthBoundary（智能体能自主到什么程度）

与 ② 正交、只缩不放：
- `Role` 决定"动作等级"（读 / 执行 / 管理 / 跨租户）；
- `CapabilityScope` 决定"功能面"（allowed_agents 白名单 + data_scope 数据域）；
- 二者取交集。CapabilityScope **绝不放大** Role 给出的权限，只能进一步收窄。

向后兼容铁律：
- `business_role` / `capability_scope` 为 NULL 时视为 `{"allowed_agents": ["*"]}`，
  即"全部智能体可见"，与本特性上线前行为完全一致；存量用户零感知。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

# ---------------------------------------------------------------- 业务角色


class BusinessRole(str, Enum):
    """岗位视角的业务角色（与 RBAC Role 正交）。"""

    DEVICE_ENGINEER = "device_engineer"        # 设备工程师
    PROCESS_ENGINEER = "process_engineer"      # 工艺工程师
    QUALITY_MANAGER = "quality_manager"        # 质量经理
    SUPPLY_MANAGER = "supply_manager"          # 供应链经理
    FINANCE_CONTROLLER = "finance_controller"  # 财务/成本控制
    PLANT_MANAGER = "plant_manager"            # 厂长/总经理
    CUSTOM = "custom"                          # 自定义（作用域全靠 capability_scope）


BUSINESS_ROLE_LABELS: dict[str, str] = {
    BusinessRole.DEVICE_ENGINEER.value: "设备工程师",
    BusinessRole.PROCESS_ENGINEER.value: "工艺工程师",
    BusinessRole.QUALITY_MANAGER.value: "质量经理",
    BusinessRole.SUPPLY_MANAGER.value: "供应链经理",
    BusinessRole.FINANCE_CONTROLLER.value: "财务成本控制",
    BusinessRole.PLANT_MANAGER.value: "厂长/总经理",
    BusinessRole.CUSTOM.value: "自定义岗位",
}


def parse_business_role(value: str | BusinessRole | None) -> BusinessRole | None:
    """宽松解析业务角色；None/空/未知 → None（= 不限制）。"""
    if value is None:
        return None
    if isinstance(value, BusinessRole):
        return value
    s = str(value).strip().lower()
    if not s:
        return None
    for r in BusinessRole:
        if r.value == s:
            return r
    return None


def business_role_label(value: str | BusinessRole | None) -> str:
    r = parse_business_role(value)
    return BUSINESS_ROLE_LABELS.get(r.value, "未设置") if r else "未设置"


# ---------------------------------------------------------------- 功能作用域

WILDCARD = "*"

#: 缺省作用域——全放行。NULL business_role / capability_scope 一律归一到它。
DEFAULT_SCOPE: dict[str, Any] = {
    "allowed_agents": [WILDCARD],
    "data_scope": {},
    "read_only_agents": [],
}


def normalize_scope(raw: Any) -> dict[str, Any]:
    """把任意来源（DB JSON / JWT payload / None）的作用域归一为标准三键 dict。

    韧性优先：结构异常一律降级为 DEFAULT_SCOPE（放行），
    绝不因脏数据把用户锁死在外面（可用性 > 严苛性；真正的隔离在 ①②ID 层）。
    """
    if not isinstance(raw, dict) or not raw:
        return dict(DEFAULT_SCOPE)
    allowed = raw.get("allowed_agents")
    if not isinstance(allowed, list) or not allowed:
        allowed = [WILDCARD]
    read_only = raw.get("read_only_agents")
    if not isinstance(read_only, list):
        read_only = []
    data_scope = raw.get("data_scope")
    if not isinstance(data_scope, dict):
        data_scope = {}
    return {
        "allowed_agents": [str(a) for a in allowed],
        "data_scope": data_scope,
        "read_only_agents": [str(a) for a in read_only],
    }


def is_unrestricted(scope: Any) -> bool:
    """是否为"全放行"作用域（含通配符）。"""
    return WILDCARD in normalize_scope(scope)["allowed_agents"]


def is_agent_allowed(scope: Any, agent_name: str) -> bool:
    """当前作用域是否允许访问指定智能体。"""
    s = normalize_scope(scope)
    allowed = s["allowed_agents"]
    return WILDCARD in allowed or agent_name in allowed


def is_agent_read_only(scope: Any, agent_name: str) -> bool:
    """该智能体在当前作用域下是否仅可读（可看结论，不可触发自主动作）。"""
    return agent_name in normalize_scope(scope)["read_only_agents"]


def visible_agents(scope: Any, all_agents: list[str]) -> list[str]:
    """按作用域过滤出可见智能体列表（前端菜单渲染用）。"""
    if is_unrestricted(scope):
        return list(all_agents)
    allowed = set(normalize_scope(scope)["allowed_agents"])
    return [a for a in all_agents if a in allowed]


# ---------------------------------------------------------------- 拒绝异常


class CapabilityDenied(PermissionError):
    """用户功能作用域不覆盖目标智能体时抛出；API 层统一转 403。"""

    def __init__(self, agent_name: str, business_role: str | None = None, username: str | None = None):
        self.agent_name = agent_name
        self.business_role = business_role
        self.username = username
        who = f"用户「{username}」" if username else "当前用户"
        role_txt = business_role_label(business_role)
        super().__init__(
            f"功能权限不足：{who}（业务角色：{role_txt}）未被授予智能体『{agent_name}』的使用权限，"
            f"请联系租户管理员在「用户权限」中调整功能作用域。"
        )


def ensure_agent_allowed(
    agent_name: str,
    scope: Any = None,
    business_role: str | None = None,
    username: str | None = None,
) -> None:
    """守卫：作用域不覆盖 agent_name 即抛 CapabilityDenied。"""
    if not is_agent_allowed(scope, agent_name):
        raise CapabilityDenied(agent_name, business_role, username)
