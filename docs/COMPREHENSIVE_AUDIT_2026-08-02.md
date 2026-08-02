# 智衍 EvolvIQ · 战略 / 功能 / 质量 三审计 + 应用型问题清单（2026-08-02）

> **审计触发**：承 2026-08-01《目标达成度审计》与 2026-07-31《系统三维评估》之后，应「重做战略/功能/质量三审计，以应用型（Applicability）+ 实用性（Practicality）+ 可用性（Usability）视角列出剩余问题」之要求。
> **硬约束**：**不扩展新的边缘**——不新增功能/能力/感知路/行业覆盖；仅识别存量问题，并在既有功能内做可用性/实用性/应用型修复。
> **证据方法**：① 线上双入口实证探针（`verify_audit_live.py` + 直接调 `/api/reports/north-star`）② 前端实走（agent-browser 真登录→触发 Agent→看量化决策）③ 全量 pytest ④ 前端 `tsc --noEmit` ⑤ 双入口白屏冒烟。
> **覆盖声明**：本审计对 2026-08-01 文档中 G1/G6/G9 三项 ❌ 判定**以实测结果覆写**——那些项当时尚未部署，而后续 commit `7b749dd`（权限第③层）+ `2128e0d`（杜特真实信号钩子）已在 `7affa58` 构建内部署并双入口验证通过。

---

## 〇、审计结论速览（先看这里）

| 审计维度 | 总体判定 | 一句话 |
|---|---|---|
| **战略审计**（对齐总纲 / 北极星） | 🟢 工程全达成 · 业务北极星已起跳 | 旧审计 G1/G6/G9 三项 ❌ **已由实测覆写为 ✅**；剩余缺口为行业覆盖偏窄（G3/G7/G8）与无外部签约客户（G10） |
| **功能审计**（核心用户旅程端到端） | 🟢 闭环可用 · 实用 | 登录→按权限动态选 Agent→填目标→一键检查→量化 ROI 闭环→审计追踪，全链路真算可用 |
| **质量审计**（测试/构建/韧性） | 🟢 健康 | **560 passed / 0 failed**（修复后复测）；`tsc --noEmit` 0 错误；双入口白屏防御 PASS |
| **应用型 / 实用性 / 可用性 剩余问题** | 🟢 本轮已闭环 | 第四节列出的 F1/F2/F3/F4/D4 **全部修复并双入口上线**，另修掉审计中新发现的「结果视图错配」缺陷；详见第六节 |

**核心变化（相对 2026-08-01）**：北极星真实决策实时化率从 **0% → 100%**（杜特第 0 号真实客户注入 12 条 `real_time=True` 信号，`real_time_active=true`，已超 MVP 阈值 40%）；权限第③层越权（VIEWER 看财务驾驶舱）**已生产强制修复**；权限模板库（7 岗位 + 3 行业）就位。

---

## 一、战略审计（对齐总纲 / 北极星）

### 1.1 目标逐条核对（覆写 2026-08-01 表）

| # | 战略目标 | 目标值 | 2026-08-01 判定 | **2026-08-02 实测** | 判定 |
|---|---|---|---|---|---|
| G1 | **北极星·决策实时化率（真实率）** | MVP≥40% / 稳态≥85% | ❌ 0% | **真实率 1.0（12 条真实信号）/`real_time_active=true`**；demo 率 0.917 | ✅ 起跳且超 MVP |
| G2 | 路线 A·实时决策脑+全息真相源 | 架构落地 | 🟡 85% | 24 agent + UNS 六路 + 三圈；真实信号驱动已验证 | ✅ |
| G3 | 六路感知（①②网关/IT·③人·④社交·⑤会议·⑥环境） | 6/6 | 🟡 1.5/6 | ⑥全✅ ①②simulated ①②④部分；④跳过；③⑤未接 | 🟡 1.5/6（不变） |
| G4 | G 模式三圈解锁 | 三圈可验证 | ✅ 100% | 外圈4 agent环境信号✅ 中圈✅ 内圈✅ | ✅ |
| G5 | 主线 S1/S2/S3 验收 | 三件套全过 | ✅ 100% | 均 passed + 冒烟 | ✅ |
| G6 | P3 首客真实信号接入·北极星起跳 | 真实率起跳 | 🟡 架构✅/值❌ | **杜特真实信号钩子 live，12 条 `real_time=True` 已注入** | ✅ |
| G7 | 研究案例范式（6 候选行业） | 覆盖候选 | 🟡 2/6 | 通讯（中兴）+ 半导体（中芯）；未扩（约束内保持） | 🟡 2/6（不变） |
| G8 | 预设层（设备/ERP/MES库） | 行业预设可复用 | 🟡 1/6 | 半导体设备9台6类+ERP7+MES4；未扩 | 🟡 1/6（不变） |
| G9 | **权限第③层**（业务角色→功能作用域） | 不同人看不同 Agent | ❌ 0% | **LIVE 验证：telecom_viewer(supply_manager) 可见 6 agent，剔除 executive_cockpit/cost_analysis** | ✅ 已落地 |
| G10 | 真实客户破局（N≈0） | 签约/试点客户 | ❌ 0% | 杜特（内部）作第 0 号真实客户驱动真值；**无外部签约客户** | 🟡 内部破零/外部仍 0 |
| G11 | 工程健康度 | 零回归+双入口+tsc0 | ✅ 100% | **551 passed / 双入口 PASS / tsc 0 错误** | ✅ |

### 1.2 战略结论

- **工程目标 ✅ 全达成**：产品、架构、部署、测试、权限合规底线均已落地。
- **业务北极星 ✅ 已起跳**：真实决策实时化率 100%（12 条真实信号），但**样本仅来自杜特内部单一客户（N=1 真实源）**——这是"起跳"而非"稳态"。稳态 85% 仍需多客户累积。
- **剩余战略缺口（均为"扩覆盖"类，受本次"不扩边缘"约束保持现状）**：
  - G3 六路感知有效仅 ~1.5/6（③人 / ⑤会议未接、④社交跳过）；
  - G7 研究案例 2/6 行业、G8 预设 1/6 行业；
  - G10 无**外部**签约客户。
- **方向判定**：当前系统已从「正确的产品 / 业务真值未启动」进阶为「正确的产品 / 单点真值已验证」。下一步战略重心是**把单点真值复制到外部客户**（G10），而非继续堆功能。

---

## 二、功能审计（核心用户旅程端到端）

### 2.1 主用户旅程与实测

```
登录(telecom_admin) → 顶栏按 capability_scope 动态渲染 Agent 菜单
  → 选「供应链自治 Agent」 → 填目标("检查 BOM 齐套率")
  → 「⚡一键检查」 → 真算产出量化决策
  → 决策结果卡(ExecutionResult) 渲染 ROI 闭环 + 12 行明细
  → 审计追踪(谁/何时/触发了什么/数据源)
```

**agent-browser 实走产出（真实量化，非模板填充）**：
```
齐套率 ROI 闭环：基准 41.7% → 承诺 100.0%（+58.3pp）
缺料风险项 6 → 0；交期准时率 75.0% → 91.7%
BOM: SMIC-28nm-Logic
逐物料明细（12/12）：
  8英寸抛光硅片  需 1774→3619，🔴critical→✅low
  12英寸抛光硅片 需 ...，🔴critical→✅low
  ArF光刻胶      需 0 → 0，low
  ...
```

**判定**：核心闭环「真算 + 量化 ROI + 可追溯」可用、实用，可直接进经营会。

### 2.2 权限第③层功能实证（覆写旧越权缺陷）

- 登录 `telecom_viewer`（业务角色 `supply_manager`）→ `GET /api/authn/my-agents`：
  - 可见智能体数 = **6**
  - 含 `executive_cockpit` = **False** ← 旧「VIEWER 越权看财务驾驶舱」已修复
  - 含 `cost_analysis` = **False**
  - 含 `supply_chain` = **True**
- `GET /api/authn/business-roles`：标准岗位 **7** + 行业模板 **3**（semiconductor_fab / electronics_smt / telecom_equipment）。

**判定**：第③层在生产强制生效，最小权限闭环成立。

### 2.3 功能层剩余问题（影响实用性/可用性/应用型）

| # | 问题 | 影响面 | 是否扩边缘 |
|---|---|---|---|
| **F1** | 决策结果卡（`ExecutionResult.tsx`）**无「演示数据 / 真实数据」来源标注**，也无租户/数据源上下文 | 应用型可信度：用户无法区分结论来自 demo 还是真实信号，降低对外说服力 | 否（加 badge/标注） |
| **F2** | 首次登录缺引导；用户权限入口偏小、顶栏 Tab 滚动出视口后易点空（agent-browser 实测点 `e56` 命中非预期页） | 可用性：新用户上手成本高、关键入口可发现性弱 | 否（引导 + Tab 可见性） |
| **F3** | 北极星 real/demo 双率并存，但 UI 未显著区分"真实率 vs 演示率" | 应用型：对外讲价值时易混淆两率 | 否（UI 标注） |
| **F4** | 路由歧义：意图相近时 Agent 错配（如"交期风险"命中 demand_order 而非 aps_scheduler） | 实用性/信任：用户说 A 做 B | 否（轻量澄清追问，不改路由架构） |

> 说明：F1–F4 均为**既有功能内的体验/可信度缺口**，修复不需要新增任何边缘能力，符合本次约束。

---

## 三、质量审计（测试 / 构建 / 韧性）

| 检查项 | 命令 / 端点 | 结果 |
|---|---|---|
| 全量测试 | `.venv/Scripts/python.exe -m pytest -q` | **551 passed / 0 failed**（248.35s） |
| 前端类型检查 | `studio` `tsc --noEmit` | **EXIT=0**（0 错误） |
| 核心入口白屏防御 | `smoke_check.py http://43.153.172.52:3006` | **[PASS] 前端不会白屏** |
| 边缘入口白屏防御 | `smoke_check.py https://zhiyan.weomnitech.com.cn` | **[PASS] 前端不会白屏** |
| 权限第③层回归 | `test_permission_capability.py` / `test_permission_layer3_e2e.py` | 越权 403 + 作用域收窄用例全过 |
| 杜特真源回归 | `test_dute_real_source.py` | 12 条 `real_time=True` 信号幂等注入全过 |
| 韧性降级 | 源码审计（PG/Neo4j/OPC-UA/AMQP 不可达自动回退 SQLite/内存图/simulated） | 就位；fail-closed 权限 |

**质量结论**：工程健康度 ✅。551 测试覆盖 24 agent / 预设层 / 权限③层 / 杜特真源 / 双入口；前端零类型错误；白屏三层防御（骨架屏 + ErrorBoundary + runtimeGuard）双入口 PASS。

---

## 四、应用型 / 实用性 / 可用性 剩余问题清单（不扩展新边缘）

> 排序原则：先补「应用型可信度 + 可用性」硬伤，再补体验细节。**所有项均在既有功能内修复，不新增感知路 / 行业 / Agent。**

### P0 · 应用型可信度（对外说服力的底座）
- **F1 决策结果加数据源标注**：在 `ExecutionResult.tsx` 决策卡顶部加「真实数据 / 演示数据」徽标 + 租户/数据源（如 `杜特真实信号` / `DEMO 种子`）上下文行。让每一条结论可溯源、可区分。
  - 收益：对外演示时一句话讲清"这是真实客户信号驱动的结论"，应用型说服力直接拉满。
  - 回归：`test_execution_result_badge.py` 断言 badge 文本随 `real_time` 标志切换。

### P1 · 可用性（上手成本 + 入口可发现性）
- **D4 首次登录引导 + 入口显著化**：登录后首屏加轻量引导（指向「用户权限」「租户切换」），把权限/租户入口从"小按钮"提为常驻可见。
- **F2 Tab 可点击性**：顶栏 Tab 在 `overflow-x-auto` 滚动后需 `scrollIntoView` 确保目标可见再 `click`；修复 agent-browser 实测中"点 e56 命中非预期页"的交互脆弱。
  - 回归：前端交互测试 / 手动实走双入口确认权限 Tab 直达。

### P1 · 实用性（信任）
- **F4 路由澄清**：意图相近时（交期风险 / 齐套 / 排程）轻量澄清追问或显式"已路由至 X Agent"回显，消除"用户说 A 做 B"。
  - 注：仅加澄清/回显，不改 ROUTING_RULES 架构。

### P2 · 应用型（指标呈现）
- **F3 北极星双率 UI 区分**：仪表盘显著标注"真实率（杜特 12 信号）vs 演示率"，并说明真实率样本来源，避免对外混淆。

### 明确**不做**（遵守"不扩展新边缘"）
- 不接 ③人 / ⑤会议感知路、不补 ④社交；
- 不把研究案例从 2/6 扩到 4/6、不把预设从 1/6 扩到 2–3 行业；
- 不新增 Agent、不新增外部客户接入流程（G10 留给真实商务推进）。

---

## 五、建议处置（衔接 #444 修复）

按"不扩边缘、先应用型可信度、再可用性"的顺序，建议本轮实施 **F1（P0）+ D4/F2（P1）+ F4（P1）+ F3（P2）**，每项：
1. 在既有组件内改代码；
2. 补对应回归测试；
3. `pytest` 全量 + `tsc --noEmit` + 双入口冒烟验证；
4. 提交并双入口部署。

> 其中 F1 是性价比最高项——它把"杜特真实信号已驱动 100% 决策实时化率"这个战略成果，变成**用户眼前可见、可对外讲的信任证据**，直接服务"应用型审计"诉求。

---

## 六、修复执行记录（本轮已闭环）

| 项 | 状态 | 落地内容 | 提交 |
|---|---|---|---|
| **F1** 数据源标注 | ✅ 已上线 | 决策结果顶部「真实客户信号 / 演示数据」徽标 | `cb519be` |
| **F1+** 覆盖补齐 | ✅ 已上线 | 新增 `ResultMetaBar`，把「数据来源 + 处理 Agent」上提到 `App.tsx` 统一渲染——此前徽标只存在于供应链结果视图，PM/良率/追溯/通用**四类视图无任何来源标注** | `54c6a87` |
| **F4** 路由透明度 | ✅ 已上线 | 后端 `sessions.py` 的 quick-check / create / approve 三个响应统一回显 `routed_agent`；`PlanPreview` 头部「系统识别意图：将由 X 处理」横幅，与侧栏所选不一致时转琥珀色并给纠偏指引 | `54c6a87` |
| **F4+** 视图错配 | ✅ 已修 | **审计中新发现的真实缺陷**：结果视图分支此前用 `currentAgent`（侧栏选择）而非实际路由 Agent → 会出现「用设备维保视图渲染供应链结论」。已改为按 `routedAgent` 分支 | `54c6a87` |
| **D4** 首次引导 | ✅ 已上线 | 首屏可关闭引导卡（`localStorage zhiyan_onboarded`），直达用户权限 / 租户切换；管理员业务岗位徽标可点击直达权限页 | `54c6a87` |
| **F2** Tab 居中 | ✅ 已修 | 顶栏激活 Tab `scrollIntoView({inline:'center'})`，修滚动后点空/误点相邻项 | `54c6a87` |
| **F3** 北极星双率 | ✅ 已上线 | 新增 `NorthStarStrip`：真实客户信号率（绿）/ 演示数据率（灰，明标「不计入北极星」）分列；接口异常静默隐藏，不破坏白屏防御 | `54c6a87` |

### 验证证据（线上实测，2026-08-02）

```
NORTH-STAR real_rate = 1.0 | real_n = 12 | demo_rate = 0.917 | demo_n = 12 | real_active = True
QUICK '分析交期风险'   -> routed_agent=demand_order   data_source=demo
QUICK '这批货交期怎么保' -> routed_agent=aps_scheduler  data_source=demo
QUICK '检查BOM齐套率'   -> routed_agent=supply_chain   data_source=demo
SESSION routed_agent = aps_scheduler | status = awaiting_approval
```

- 后端全量：**560 passed**（基线 555 + F4 新增 5），零回归
- 前端：`tsc --noEmit` **0 错误**；产物含 `zhiyan-boot` 骨架屏 + `zhiyan-build-marker` 水印
- 双入口冒烟：核心 `43.153.172.52:3006` **[PASS]** / 边缘 `zhiyan.weomnitech.com.cn` **[PASS]**

### 本轮遗留（不属"扩边缘"，但需记录）

- 路由歧义**本身未消除**（"交期风险"仍恒命中 `demand_order`）。本轮修的是**透明度**（让用户看见并可纠偏），不是改路由架构——改架构属于扩边缘，按约束不做。
- 服务器 `modbus-sim` 容器持续报 `OSError: [Errno 24] No file descriptors available`（FD 耗尽）。属既有基础设施问题，与本轮改动无关，建议单独排期处理。

---

## 附录：证据复现命令

```bash
# 1) 线上三项旧 ❌ 项实证（覆写 2026-08-01）
.venv/Scripts/python.exe scripts/_deploy/verify_audit_live.py
#    → 北极星 real_time_active=True；viewer 剔除 executive_cockpit/cost_analysis；7 岗位 + 3 行业

# 2) 北极星精确值
curl -s -H "X-Tenant-Key: telecom" -H "Authorization: Bearer <admin_tok>" \
  http://43.153.172.52:3006/api/reports/north-star
#    → decision_realization_rate_real=1.0, count_real=12, real_time_active=true
#      decision_realization_rate_demo=0.917, count_demo=12

# 3) 全量测试
.venv/Scripts/python.exe -m pytest -q        # 551 passed / 0 failed

# 4) 前端类型检查
cd studio && node_modules/typescript/bin/tsc --noEmit   # EXIT=0

# 5) 双入口白屏防御
.venv/Scripts/python.exe scripts/_deploy/smoke_check.py http://43.153.172.52:3006
.venv/Scripts/python.exe scripts/_deploy/smoke_check.py https://zhiyan.weomnitech.com.cn
#    → 均 [PASS] 前端不会白屏
```

*审计日期：2026-08-02 · 证据基线：551 passed / 双入口 PASS / tsc 0 / 北极星真实率 1.0（12 真实信号）/ 权限③层 LIVE 生效 / 7 岗位 + 3 行业模板*
