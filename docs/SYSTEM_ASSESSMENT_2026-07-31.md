# 智衍 EvolvIQ 系统三维评估与综合统一规划

> 评估日期：2026-07-31
> 评估方法：基于真实系统状态（生产双入口 / 代码 / 全量测试 / 前端构建），所有状态结论均来自实测证据，不采信文档声明。
> 评估维度：① 可用性（Usability）② 实用性（Practicality）③ 应用性（Applicability）

---

## 执行概要（结论先行）

| 维度 | 总体判定 | 核心结论 |
|---|---|---|
| **可用性** | 🟡 良好但有安全缺口 | 部署/前端/登录/租户切换均可用；**权限第③层（业务角色→功能作用域）仅 PRD 未落地**，VIEWER 当前可看全厂财务驾驶舱——越权风险 |
| **实用性** | ✅ 扎实 | 24 智能体 + 预设层（设备9/ERP7/MES4）+ 研究案例范式 + 北极星埋点 + 可对外定价，已具备"选型号即对接、数日出结论"的实用闭环 |
| **应用性** | 🟡 单行业验证 | 半导体行业完整闭环（设备+案例+试点管线）；其余 5 候选行业预设待建；企业入驻框架就位但待真实客户验证 |

**本轮发现的真实缺陷（已修复 1 项）**：
- ✅ `test_pm_agent.py:22` 断言 `==3` 与扩设备到 9 台冲突 → 已改为绑定 `PROFILES` 数量，复跑 3 passed。
- 🔴 权限第③层未落地（仅 `PERMISSION_ARCHITECTURE_PRD.md`），属安全/合规缺口，需优先处理。

**全量测试基线**：`475 passed / 0 failed`（修复后）。

---

## 一、可用性评估（Usability）

### 1.1 部署与前端可运行性 ✅

| 证据 | 结果 |
|---|---|
| 核心入口冒烟 `http://43.153.172.52:3006` | `[PASS] 冒烟门禁通过：前端不会白屏` |
| 边缘入口冒烟 `https://zhiyan.weomnitech.com.cn` | `[PASS] 冒烟门禁通过：前端不会白屏` |
| 前端 TypeScript 类型检查 `tsc --noEmit` | `EXIT:0`（0 错误） |
| 前端关键组件存在性 | `Login.tsx` `TenantSwitcher.tsx` `TenantManagement.tsx` `AgentSidebar.tsx` `TwinDashboard.tsx` 全部存在 |

**结论**：系统可部署、可构建、可登录，双入口白屏防御三层就位（骨架屏 + ErrorBoundary + runtimeGuard），可用性底座扎实。

### 1.2 多租户切换 ✅（含一次自我纠正）

- `src/components/TenantSwitcher.tsx` 已接入主布局 `src/App.tsx:259`，顶栏 🏢 下拉列出全部租户、可一键切换、数据按租户硬隔离。
- 登录链路 `Login.tsx:22` → `onLogin(access_token, user)` 回调在父层注入 token，鉴权三铁律生效。
- **自我纠正**：此前诊断曾称"前端无租户切换入口"，经查证该组件已存在并接入布局——该判断有误。杜特租户"看不到"的真实原因更可能是**入口不够显著（小按钮）或未被注意到**，而非功能缺失。

### 1.3 权限精细化 🔴（关键缺口）

| 检查项 | 证据 | 状态 |
|---|---|---|
| 第③层 `require_capability` / `business_role` / `capability_scope` | `grep -rn` 全 `src/` 无匹配 | **未落地，仅 PRD** |
| 现有 RBAC 角色 | `authn/roles.py`：VIEWER/OPERATOR/TENANT_ADMIN/SUPERADMIN | ✅ 4 级 |
| Agent 授权边界 | `authorization.py` TenantAuthScope（22 agent 读写执行） | ✅ 租户级 |
| 租户隔离 | `context.py` + `X-Tenant-Key` fail-closed | ✅ 企业间隔离 |

**问题本质**：现有三层（租户隔离 / IT 角色 / Agent 动作边界）管的是"谁能登录、谁能执行"，**没管"谁看得到哪个 Agent"**。当前 VIEWER 登录后能看到 `executive_cockpit`（财务经营驾驶舱）、`cost_analysis`（成本分析）等敏感面板——一个车间设备员不该看到全厂财务数据。这违反最小权限原则，且在多用户入驻场景下是合规硬伤。

### 1.4 可发现性 🟡

租户切换、Agent 面板均可用，但入口偏小、缺乏首次登录引导。建议后续优化（P2）。

---

## 二、实用性评估（Practicality）

### 2.1 智能体覆盖度 ✅

`src/runtime/agent/router.py:39-71` 注册 **24 个 Agent**，场景覆盖：

```
设备层：  pm_maintenance · oee_optimizer · smt_changeover · aoi_judge
质量层：  yield_analysis · quality_trace · dfm_check · eco_change · ipc_standard
经营层：  executive_cockpit · cost_analysis · aps_scheduler · demand_order
         wms_logistics · procurement_manage · rd_npi · compliance_q
供应链：  supply_chain · bom_selector
可持续：  energy_carbon
研究范式：industry_research · case_curator · enterprise_onboarding · compliance_reviewer
```

制造业主要决策场景全覆盖，且每个 Agent 自带行业种子数据与推理能力（非 SQL 查询）。

### 2.2 预设层（AI 智能体时代的"预设"）✅

| 预设类别 | 套数 | 代码位置 | 覆盖度 |
|---|---|---|---|
| 设备库 | 9 台（6 大类） | `pm_maintenance/equipment_profiles.py` | 半导体 Fab 全覆盖 |
| ERP 库 | 7 | `presets/erp_profiles.py` | 中国制造业 90%+ |
| MES 库 | 4 | `presets/mes_profiles.py` | 进口+国产 85%+ |

`get_preset_summary()` 实测：`ERP:7 MES:4 设备:9 台`。客户入驻时"选型号即对接"，边际接入成本趋零——这是相对传统项目制交付的核心差异化。

### 2.3 研究案例范式 ✅

- 两个真实锚定案例入库：`case_telecom_2026`（中兴）、`case_semicon_2026`（中芯国际，内部锚定）。
- 腿 A 实证：`LEG_A_FORWARD_VALIDATION_ZTE.md` 回看 ZTE 2024-2025-2026Q1，5/5 descriptive 断言方向正确。
- 腿 B 试点：`pilot_ring` 管线 + `_scrub` 匿名擦洗 + `pilot_hooks`（网关 simulated / 北极星埋点，铁律①只建钩子不实测）。

### 2.4 北极星指标与定价 ✅

- 决策实时化率埋点：`metrics.py:140 record_decision_realization` + `:159 north_star_report`，待 `ZHIYAN_DEMO_DATA=0` 起跳。
- 对外定价：`PRICING_MODEL.md` 定调版（中圈 ¥2,480/月 = 西门子同级 80%；内圈 ¥168,000 部署 + ¥98,000/年）。

### 2.5 实用性缺口 🟡

真实信号闭环未起跳：外圈免费版已就位，但真实客户驱动决策尚未发生，北极星仍 0%。这是"可用性已具备、应用性待验证"的中间态——不阻碍交付，但需在真实客户入驻后观测。

---

## 三、应用性评估（Applicability）

### 3.1 行业覆盖 🟡

| 行业 | 设备预设 | 案例 | 状态 |
|---|---|---|---|
| 半导体 | ✅ 6 类 9 台 | ✅ 中芯国际（试点 P3） | 完整闭环 |
| 通讯 | — | ✅ 中兴（腿 A 实证） | 案例有、设备预设待补 |
| 3C / 新能源 / 光伏 / 工程机械 | — | — | 候选池，待建 |

候选池共 6 行业（半导体/3C/新能源汽车/通讯/光伏/工程机械），当前仅半导体打通端到端。

### 3.2 企业入驻与合规 🟡→✅

- 两阶段实例化框架 `enterprise_onboarding` 就位（公开预载 → 企业声明式描述 + 凭证实例化）。
- 合规闸门 `compliance_reviewer`：匿名/真名双版边界 + 零泄漏 + research_case 纪律，已测试。
- 数据卫生：已清理 PostgreSQL 残留租户，杜特租户（`dute` / 上海杜特企业管理咨询有限公司）健康，3 账号登录验证通过。

### 3.3 部署架构 ✅

Docker + nginx 反代 + 双入口（核心 43.153.172.52:3006 / 边缘火山 HTTPS）+ 韧性降级（PG/Neo4j/OPC-UA/AMQP 不可达自动回退），生产就绪。

### 3.4 应用性缺口 🔴

权限模板库未建：与设备库/ERP库/MES库**同构**的 `presets/permission_templates.py`（半导体 Fab 标准权限模板）尚未创建。新客户入驻时无法"勾选业务角色模板"，仍需从零配权限。

---

## 四、发现的真实缺陷与处理

| # | 缺陷 | 严重性 | 处理 |
|---|---|---|---|
| D1 | `test_pm_agent.py:22` 断言 `==3`，与设备扩至 9 台冲突 | 低（测试卫生） | ✅ 已改为绑定 `len(PROFILES)`，复跑 3 passed |
| D2 | 权限第③层（业务角色→功能作用域）仅 PRD，未落地 | **高（越权/合规）** | 🔴 待统一规划 P0 落地 |
| D3 | 预设层扩展时测试同步机制缺失（D1 即教训） | 中 | 🟡 统一规划 P1 补"预设扩展测试契约" |
| D4 | 租户切换入口不显著，杜特租户"看不到" | 低（可发现性） | 🟡 统一规划 P2 优化 |

---

## 五、综合统一规划（统一处理路线图）

> 原则：**把"权限模板"与"设备/ERP/MES 预设"同构处理**——预设哲学从数据层推到权限层；所有扩展走同一套"先建模板、客户勾选"机制。

### P0 · 安全与合规底线（必须优先）

**P0-1 权限第③层后端闭环**（复用现有架构，不另起炉灶）
- `User` 模型加 `business_role` + `capability_scope`（Alembic 迁移，null scope 默认全可见，老用户不破）
- JWT payload 注入 `capability_scope`
- 新增 `require_capability(agent_name)` 依赖（仿 `require_role`）
- `engine.py:273` 取 boundary 前先过 capability 拦截（无权限 Agent 不调度，直接 403）
- 测试：7 条用例（含越权 403 验证）

**P0-2 权限模板库（预设化）** `presets/permission_templates.py`
- 半导体 Fab 标准权限模板：设备工程师 / 工艺师 / 质量经理 / 供应链经理 / 财务总监 / 厂长 六角色 → 可见 Agent 集合 + 数据域
- 与设备库同构：入驻时勾选即完成权限配置

### P1 · 实用性闭环与扩展

**P1-1 行业预设扩展**（按"先有后优"顺序）
- 通讯（中兴案例已有 → 补设备预设）
- 3C → 新能源汽车 → 光伏 → 工程机械
- 每行业复制"设备+ERP+MES"三件套模板

**P1-2 预设扩展测试契约**（防 D1 重演）
- 新增 `tests/test_preset_contract.py`：断言每套预设含 data_domains / agent_mapping / connection 三要素；设备数变更时强制同步测试

**P1-3 北极星真实起跳**
- 评估 `ZHIYAN_DEMO_DATA=0` 切换时机（遵守铁律①：外部接口只建钩子不实测）
- 真实客户入驻后观测决策实时化率从 0% 起跳

### P2 · 可用性与体验

**P2-1 可发现性优化**
- 租户切换入口更显著（顶栏常驻 + 首次登录引导）
- Agent 侧边栏按 `capability_scope` 动态渲染（P0 落地后接）

**P2-2 统一规划文档收口**
- 本评估 + 权限 PRD + 预设层指南 → 合并进 `MASTER_EXECUTION_PLAN.md` 新增「预设层总纲」章节

---

## 附录：证据复现命令

```bash
# 双入口冒烟
./.venv/Scripts/python.exe scripts/_deploy/smoke_check.py http://43.153.172.52:3006
./.venv/Scripts/python.exe scripts/_deploy/smoke_check.py https://zhiyan.weomnitech.com.cn

# 前端类型检查
cd studio && /c/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2/node.exe node_modules/typescript/bin/tsc --noEmit

# Agent 注册表
grep -n "AGENT_REGISTRY" src/runtime/agent/router.py   # 24 个

# 预设层
./.venv/Scripts/python.exe -c "from src.presets import get_preset_summary as s; print(s())"

# 权限缺口
grep -rn "require_capability\|business_role\|capability_scope" src/   # 空=未落地

# 全量测试
./.venv/Scripts/python.exe -m pytest tests/ -q   # 475 passed / 0 failed
```
