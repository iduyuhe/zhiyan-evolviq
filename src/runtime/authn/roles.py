"""RBAC 角色定义与层级

角色从低到高（数字越大权限越高）：

    viewer(0) < operator(1) < tenant_admin(2) < superadmin(3)

语义：
- viewer：只读（看大屏、看会话、看知识图谱）
- operator：可执行 Agent 任务、发起会话、查看/审批干预
- tenant_admin：管理本租户用户、数据源、授权边界
- superadmin：跨租户管理、平台级配置、用户角色变更

`require_role(min_role)` 依赖按 rank 比较，当前用户 rank >= min 即通过。
"""

from enum import IntEnum


class Role(IntEnum):
    VIEWER = 0
    OPERATOR = 1
    TENANT_ADMIN = 2
    SUPERADMIN = 3


# 角色中文名（对外展示 / 日志）
ROLE_LABELS = {
    Role.VIEWER: "访客",
    Role.OPERATOR: "操作员",
    Role.TENANT_ADMIN: "租户管理员",
    Role.SUPERADMIN: "超级管理员",
}

# 从字符串解析（兼容 "tenant_admin" / "TENANT_ADMIN" / 枚举名）
_ROLE_BY_NAME = {r.name.lower(): r for r in Role}
_ROLE_BY_NAME.update({r.name: r for r in Role})


def parse_role(value: str | Role | int) -> Role:
    """把任意形式（字符串 / 枚举 / int）的角色归一为 Role。非法值抛 ValueError。"""
    if isinstance(value, Role):
        return value
    if isinstance(value, int):
        return Role(value)
    s = str(value).strip().lower()
    if s.isdigit():
        return Role(int(s))
    if s not in _ROLE_BY_NAME:
        raise ValueError(f"未知角色: {value!r}（可选: {[r.name for r in Role]}）")
    return _ROLE_BY_NAME[s]


def role_rank(value) -> int:
    return int(parse_role(value))


def role_label(value) -> str:
    return ROLE_LABELS[parse_role(value)]


def has_role(current, minimum) -> bool:
    """当前角色是否达到最低要求角色。"""
    return role_rank(current) >= role_rank(minimum)
