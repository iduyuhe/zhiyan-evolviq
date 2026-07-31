# 智衍 EvolvIQ · 企业内多用户差异化权限架构设计（PRD）

> 状态：🔵 设计文档（2026-07-31 杜总定调「先出设计文档，审定后再落地」）
> 作者：智衍平台架构组
> 关联战略：`MASTER_EXECUTION_PLAN.md` §3「无感转型」+ 预设层战略（设备库/ERP库/MES库/权限模板库同构）
> 关联代码：`src/runtime/authn/`、`src/runtime/core/authorization.py`、`src/runtime/agent/engine.py`、`src/runtime/context.py`

---

## 1. 背景与问题

### 1.1 杜总原话

> 「对于这么多智能体，作为企业内部的话，怎么样让不同的人有不同的权限。」

### 1.2 问题本质

现有平台权限是 **IT 治理视角**（管"谁能登录、谁管用户、哪个 Agent 能自主执行动作"），但杜总问的是 **业务功能视角**（"不同的人看不同的东西"）——这两套视角之间缺一座桥。

**具体症状**：当前 `VIEWER`（访客）角色登录后，能看到全部 22 个 Agent 的输出，包括 `executive_cockpit`（财务经营驾驶舱）、`cost_analysis`（成本分析）等敏感面板。一个车间设备员不应看到全厂财务数据。

### 1.3 根因

`Role`（`src/runtime/authn/roles.py`）是 IT 概念（VIEWER/OPERATOR/TENANT_ADMIN/SUPERADMIN），解决"操作能力与管理权限"；业务是另一套概念（设备工程师/工艺师/财务总监/厂长），解决"可见 Agent 集合与数据域"。**两者之间目前没有映射层。**

---

## 2. 设计目标

| # | 目标 | 说明 |
|---|---|---|
| G1 | 业务角色隔离 | 不同职能用户只看到自己职责范围内的 Agent |
| G2 | 数据域隔离 | 同一 Agent 内，按数据域过滤（如设备工程师只看本车间） |
| G3 | 复用现有架构 | 不另起炉灶，桥接现有 RBAC + AuthBoundary + 租户隔离 |
| G4 | 预设化 | 权限模板与设备/ERP/MES 预设同构，入驻时勾选而非从零配 |
| G5 | 向后兼容 | 未配置 capability_scope 的用户默认行为不破坏 |

---

## 3. 现状盘点（三层已有 + 缺口）

| 层 | 机制 | 代码位置 | 状态 |
|---|---|---|---|
| ① 租户隔离 | `X-Tenant-Key` fail-closed，钉死请求上下文 | `src/runtime/context.py`、`src/runtime/api/auth.py` | ✅ 企业间硬隔离 |
| ② 用户 RBAC 角色 | 4 级阶梯 VIEWER→SUPERADMIN，`require_role(min)` 门禁 | `src/runtime/authn/roles.py`、`deps.py`、`api.py` | ✅ IT 角色 |
| ③ **业务角色+功能作用域** | **用户 → 可见 Agent 集合 + 数据域** | **无** | 🔴 **缺口** |
| ④ Agent 授权边界 | 22 Agent 读/写/执行、动作审批、日限额、品类白名单 | `src/runtime/core/authorization.py`、`agent/engine.py:273` | ✅ 租户级动作审批 |

**结论**：缺的是第③层——把"业务角色"映射为"功能作用域"的桥。

---

## 4. 目标架构（四层模型）

```
企业租户（tenant_id 钉死，①层隔离）
│
├─ ② 用户 RBAC 角色（IT 视角）
│     VIEWER → OPERATOR → TENANT_ADMIN → SUPERADMIN
│     控制：能否登录 / 能否执行 Agent / 能否管用户
│
├─ ③ 业务角色 + 功能作用域 ★新增（业务视角）
│     device_engineer → {allowed_agents:[pm_maintenance,energy_carbon,oee_optimizer], data_scope:{workshop:"A"}}
│     finance_controller → {allowed_agents:[executive_cockpit,cost_analysis], data_scope:{plant:"all"}}
│     控制：能看到哪些 Agent / 能看到哪些数据域
│
└─ ④ Agent 授权边界（租户级）
      supply_chain / pm_maintenance / ... 各自 read/write/execute + 审批
      控制：Agent 被允许自主执行什么动作
```

**两层正交**：一个用户同时拥有 `Role`（操作能力）与 `BusinessRole+CapabilityScope`（可见性）。`require_role` 查前者，`require_capability` 查后者。

---

## 5. 核心概念

### 5.1 BusinessRole（业务角色枚举）

与 `Role` 正交，定义在 `src/runtime/authn/roles.py` 同目录新增 `business_roles.py`：

```python
class BusinessRole(str, Enum):
    DEVICE_ENGINEER = "device_engineer"        # 设备工程师
    PROCESS_ENGINEER = "process_engineer"      # 工艺师
    QUALITY_MANAGER = "quality_manager"        # 质量经理
    SUPPLY_MANAGER = "supply_manager"          # 供应链经理
    FINANCE_CONTROLLER = "finance_controller"  # 财务总监
    PLANT_MANAGER = "plant_manager"            # 厂长（全可见+审批）
    CUSTOM = "custom"                           # 自定义（capability_scope 手写）
```

### 5.2 CapabilityScope（功能作用域）

```python
@dataclass
class CapabilityScope:
    allowed_agents: list[str]        # 白名单；含 "*" 表示全部
    data_scope: dict                 # 数据域过滤，如 {"workshop":"A"} / {"plant":"all"}
    read_only_agents: list[str]      # 其中哪些仅只读（即使 Role 允许执行）
```

### 5.3 预设映射（标准业务角色 → 作用域）

| BusinessRole | allowed_agents | data_scope |
|---|---|---|
| device_engineer | pm_maintenance, energy_carbon, oee_optimizer | workshop（用户级） |
| process_engineer | quality_trace, smt_changeover, ipc_standard | line（产线级） |
| quality_manager | quality_trace, aoI_judge, compliance_q | plant（全厂质量域） |
| supply_manager | supply_chain, demand_order, bom_selector | plant（物料/订单域） |
| finance_controller | executive_cockpit, cost_analysis | plant（经营域） |
| plant_manager | *（全部） | plant（全厂） |

---

## 6. 数据模型变更

`src/runtime/authn/models.py` 的 `User` 表新增两列（Alembic 迁移）：

```python
class User(Base):
    # ... 现有字段 ...
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.OPERATOR)
    business_role: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 新增
    capability_scope: Mapped[dict | None] = mapped_column(JSON, nullable=True)     # 新增
```

**兼容性**：`capability_scope=None` → 视为"全部可见"（保持现有行为），确保老用户/种子账号不破。

---

## 7. 认证 / JWT 变更

`src/runtime/authn/service.py` 签发 JWT 时注入 `business_role` 与 `capability_scope`：

```python
payload = {
    "sub": username, "uid": user_id,
    "role": role.name,
    "business_role": user.get("business_role"),
    "capability_scope": user.get("capability_scope") or {"allowed_agents": ["*"], "data_scope": {}},
    "tenant_id": tenant_id, "auth_source": source,
}
```

`get_current_user`（`deps.py`）原样返回该 payload，下游依赖直接消费。

---

## 8. 后端拦截点

### 8.1 新增 `require_capability` 依赖（`src/runtime/authn/deps.py`）

```python
def require_capability(agent_name: str):
    """功能作用域门禁：当前用户 capability_scope.allowed_agents 含该 agent 才放行。"""
    def dep(u: dict = Depends(get_current_user)):
        scope = u.get("capability_scope") or {}
        allowed = scope.get("allowed_agents", [])
        if "*" not in allowed and agent_name not in allowed:
            raise HTTPException(status_code=403, detail=f"无权限访问智能体 {agent_name}")
        return u
    return dep
```

### 8.2 Agent 调度拦截（`src/runtime/agent/engine.py` 约 273 行前）

在 `authorization.for_tenant(tenant_id)` 取边界**之前**，先过用户级功能作用域：

```python
# ── 新增：用户级功能作用域检查（第③层）──
from src.runtime.authn.context import get_current_capability
cap = get_current_capability()  # contextvar，由依赖注入
if cap and "*" not in cap.get("allowed_agents", []) and agent_name not in cap.get("allowed_agents", []):
    logger.warning(f"⚠️ 用户 {uid} 无 {agent_name} 功能权限，跳过调度")
    return [], []   # 或 raise HTTPException(403)
# ── 原有：租户级授权边界 ──
auth_scope = authorization.for_tenant(tenant_id)
```

`src/runtime/authn/context.py` 新增 `current_capability` contextvar（与 `context.py` 租户上下文同构）。

### 8.3 数据域过滤（可选 Phase 2 增强）

`data_scope` 透传至 Agent 工具层，过滤返回数据（如设备工程师只查本车间设备）。Phase 1 可先只做"Agent 可见性"，数据域过滤作为后续增强。

---

## 9. API 设计

在 `src/runtime/authn/api.py` 扩展（复用现有 `require_role` 保护）：

| Method | Path | 说明 | 保护 |
|---|---|---|---|
| POST | `/authn/users` | 建用户，req 加 `business_role` + `capability_scope` | tenant_admin |
| GET | `/authn/me` | 返回当前用户含 `capability_scope`（前端侧边栏消费） | 登录即可 |
| POST | `/authn/users/{id}/business-role` | 改业务角色（套用预设模板或自定义） | tenant_admin |
| GET | `/authn/capability-templates` | 列出权限预设模板（与行业预设同构） | tenant_admin |

---

## 10. 前端动态渲染

`studio/src` 侧边栏 Agent 列表从 `/authn/me` 读取 `capability_scope.allowed_agents`，**只渲染白名单内 Agent**；非白名单 Agent 不显示入口（而非显示后 403）。

- 未配置（null）→ 显示全部（兼容）
- `*` → 显示全部
- 具体列表 → 仅显示列表项

---

## 11. 与预设层结合：权限模板库 ★战略呼应

杜总 2026-07-29 定调「预设层」——设备库/ERP库/MES库先建好，客户来了直接匹配。**权限也要进预设层**：

新增 `src/presets/permission_templates.py`，与 `erp_profiles.py` / `mes_profiles.py` 同构：

```python
PERMISSION_TEMPLATES = {
    "semiconductor_fab": {                    # 半导体晶圆厂标准权限模板
        "device_engineer":   {"allowed_agents": ["pm_maintenance","energy_carbon","oee_optimizer"], "data_scope": {"workshop": "user"}},
        "process_engineer":  {"allowed_agents": ["quality_trace","smt_changeover","ipc_standard"], "data_scope": {"line": "user"}},
        "quality_manager":   {"allowed_agents": ["quality_trace","aoi_judge","compliance_q"], "data_scope": {"plant": "all"}},
        "supply_manager":    {"allowed_agents": ["supply_chain","demand_order","bom_selector"], "data_scope": {"plant": "all"}},
        "finance_controller":{"allowed_agents": ["executive_cockpit","cost_analysis"], "data_scope": {"plant": "all"}},
        "plant_manager":     {"allowed_agents": ["*"], "data_scope": {"plant": "all"}},
    },
    # 下一个行业复用同构：3C / 新能源 / 通讯 ...
}
```

**入驻流程变为**：企业入驻 → 勾选行业权限模板 → 为每个员工指派业务角色 → capability_scope 自动套用。权限配置从"定制项目"变为"模板勾选"。

---

## 12. 迁移与兼容性

1. Alembic 迁移：`User` 加 `business_role`（nullable）、`capability_scope`（JSON nullable）。
2. 种子账号（`seed_dute.py`）：杜特团队账号保留 `capability_scope=None`（全可见），SUPERADMIN 不受影响。
3. 老租户用户：`capability_scope=None` → 默认全可见，行为不变。
4. `require_capability` 仅在显式声明 agent 门禁的路由上使用；未声明的路由维持 `require_role` 现状。

---

## 13. 测试策略

新增 `tests/test_permission_capability.py`：

- `test_require_capability_allows_whitelisted`：白名单内 Agent 放行
- `test_require_capability_blocks_unlisted`：非白名单 403
- `test_require_capability_wildcard`：`*` 放行全部
- `test_engine_blocks_unauthorized_agent`：engine 调度拦截非白名单 Agent
- `test_jwt_injects_capability_scope`：登录后 `/authn/me` 含 capability_scope
- `test_compat_null_scope_sees_all`：null scope 向后兼容全可见
- `test_permission_template_applies`：权限模板套用正确

全量回归：`pytest tests/ -q` 零回退。

---

## 14. 实施阶段与验收

| 阶段 | 范围 | 验收 |
|---|---|---|
| **P1 后端闭环** | 模型迁移 + JWT 注入 + `require_capability` + `engine.py` 拦截 + `context.py` capability contextvar | 后端权限闭环，测试全绿，部署双入口冒烟 PASS |
| **P2 前端渲染** | 侧边栏按 `capability_scope` 动态渲染 | 不同角色登录看到不同 Agent 列表 |
| **P3 预设化** | `permission_templates.py` + 入驻流程勾选 + API 模板列表 | 新企业入驻勾选行业权限模板即完成权限配置 |

**建议首交付**：先落地 **P1**（后端闭环），因为后端拦截是安全底线，且不影响现有前端行为（前端仍显示全部，只是后端已拦截越权调用）。P2/P3 可随后迭代。

---

## 15. 风险与权衡

| 风险 | 缓解 |
|---|---|
| capability_scope 与 Role 冲突（Role=OPERATOR 但业务角色只读） | 两层取交集：最终权限 = Role ∩ CapabilityScope。CapabilityScope 只缩不减 |
| 数据域过滤复杂度高（Phase 2） | Phase 1 仅做 Agent 可见性，数据域过滤作为增强，不阻塞首交付 |
| 老用户 null scope 全可见的安全暴露 | 明确为"兼容过渡态"；建议 TENANT_ADMIN 在入驻后 30 天内补全 business_role |
| 权限模板与行业预设不同步 | 权限模板随行业预设库一同扩展（同一 PR 评审） |

---

## 附录 A：与既有架构的依赖关系图

```
src/runtime/authn/
├── roles.py            (现有 Role 4级)
├── business_roles.py   (新增 BusinessRole 枚举)  ← ③层
├── models.py           (User +business_role +capability_scope)
├── service.py          (JWT 注入 capability_scope)
├── deps.py             (新增 require_capability)
├── context.py          (新增 current_capability contextvar)
└── api.py              (扩展建用户/改业务角色/模板列表)

src/runtime/core/authorization.py   (④层 租户级 Agent 边界，不动)
src/runtime/agent/engine.py         (273行前插入 ③层 用户级拦截)
src/runtime/context.py              (①层 租户隔离，不动)

src/presets/
├── erp_profiles.py     (现有)
├── mes_profiles.py     (现有)
└── permission_templates.py  (新增 权限预设，同构)  ← ③层预设化
```

---

## 附录 B：典型场景验证

**场景**：某半导体 Fab 入驻，设备工程师张三、财务总监李四。

| 用户 | business_role | 登录后可见 Agent | 点 executive_cockpit |
|---|---|---|---|
| 张三 | device_engineer | pm_maintenance, energy_carbon, oee_optimizer | 前端不显示；若直调 API → 403 |
| 李四 | finance_controller | executive_cockpit, cost_analysis | 正常显示全厂经营数据 |

**验证点**：张三无法通过任何路径（前端入口 / 直调 API / Agent 调度）触达 `executive_cockpit`——三层防线（前端隐藏 + API 403 + engine 拦截）同时生效。
