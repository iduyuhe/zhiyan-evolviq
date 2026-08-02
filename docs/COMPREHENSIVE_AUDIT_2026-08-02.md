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

---

## 七、研究案例库加强（应用型第二弹，2026-08-02 续）

> **触发**：用户实拍截图反馈「研究案例库做的太简单了，不是加分项都变成减分项，需要进一步加强」。
> **约束**：仍守「不扩展新边缘」——不新增案例/行业/Agent，只解锁既有内容+改渲染。

### 7.1 现状摸底（挖出的「肥肉」）

| 维度 | 实测 |
|---|---|
| 后端数据体量 | 4 案例共 **59 条公开披露事实 + 22 条多维推演结论**（合计 10,878 字符）|
| API 暴露缺口 | `_case_detail()` 白名单**主动丢弃** `disclosure_facts` + `derived_insights`，详情抽屉只看到 5 个推荐接口 chip + 1 段教学笔记 |
| 死库存 | 3C / 新能源两个案例**根本没绑定租户**（`/cases/my` 走不通），但 `cases.json` 里数据是全的 |
| 前端渲染缺口 | 列表卡片只用 `subject_anon / industry / status / updated_at` 4 字段；`status` 已声明在 TS 接口但 JSX 从未渲染；`derived_insights.assertion_type` + `value_judgment` 完全未声明 |
| 现成 JSX | 「我的绑定案例」区块（149-201 行）**早就写好**了财报表+结论卡渲染，因没数据只在绑定租户处可见 |

### 7.2 修复清单（提交 `d577a43`）

| 项 | 内容 | 落地位置 |
|---|---|---|
| F1+ | 后端 `_case_detail()` 白名单补 `disclosure_facts` + `derived_insights` | `agent.py:548-568`（+2 字段） |
| F1+ | 后端 `_list_cases()` 列表项补 `fact_count` + `insight_count` | `agent.py:565-587`（+2 字段） |
| F1+ | `DerivedInsight` TS 接口补 `assertion_type` + `value_judgment` | `CaseLibraryPanel.tsx:32-37` |
| F2+ | 列表卡片加**行业色条** + 事实/结论计数角标 + status 徽标 | `CaseLibraryPanel.tsx:268-307` |
| F2+ | 详情抽屉头部加行业色条 + status 徽标 | `CaseLibraryPanel.tsx:331-341` |
| F3+ | 详情抽屉渲染财报表 + 推演结论区 | `CaseLibraryPanel.tsx:343-450`（复用+升级）|
| F3+ | 推演按 `value_judgment`（high→medium→low）+ `assertion_type`（predictive 优先）排序 | `sortInsights()`（新工具函数）|
| F3+ | 推演按 `dimension` 着色（6 维色系） + 高价值左侧色条 + 「🔮 前瞻预判」「⚡ 高价值」徽标 | `DIM_COLOR` + 抽屉渲染 |
| F3+ | 教学笔记块加蓝底浅色块容器，提升可读性 | 抽屉底部 |
| F4+ | 「我的绑定案例」同步升级到新排序+着色体系 | `CaseLibraryPanel.tsx:179-225` |
| 测试 | 新增 3 例：列表计数 / 详情放行 / 真名不外泄双保险 | `test_library_and_case_tenants.py` |

### 7.3 验证证据

| 检查 | 结果 |
|---|---|
| 全量 pytest | **563 passed**（基线 560 + 本轮 3）/ 0 failed / 246s |
| tsc --noEmit | 0 错误 |
| vite build | ✅ 530KB js + 59KB css（白屏防御标记在） |
| 核心部署 | `d577a43` 上线（runtime+studio 双容器重建） |
| 边缘同步 | release=`d577a43`（首次 502 触发自动回滚→轮询 200 后重试成功）|
| 双入口冒烟 | 核心 43:3006 ✅ / 边缘 weomnitech ✅ |

### 7.4 守住的边界

- **零新数据**：没新增任何案例/事实/结论，全部从 `cases.json` 既有 10,878 字符里挖。
- **零新接口**：3 个既有端点（`/cases/library` / `/cases/library/{id}` / `/cases/my`）的字段放行 + 计数计算。
- **零新组件**：`CaseLibraryPanel.tsx` 单文件改造，无新文件、无 App.tsx 改动。
- **匿名合规双保险**：`_case_detail()` 永远不放行 `real_anchor`；3 个新测试 + 既有 `_assert_no_leak()` 矩阵确保 4 案例的详情 payload **零真名**。
- **既有 UX 守恒**：交互（点击卡片开抽屉 / 关抽屉 / 「我的绑定案例」位置）一字未动；强化的是**信息密度**，不是**操作流程**。

### 7.5 留下的肥肉（不扩边缘，故不动）

- `_search_cases()` 中文滑窗模糊搜索（agent 端已实现，`_list_cases` 旁的同模块方法）——未暴露成 REST。
- `_recommended_interfaces()` 跨案例汇总接口 —— agent 端已实现，未暴露。
- `cases.json` 还有 `teaching_notes_internal` 真名版（合规隔离用）—— 故意不暴露，留给 `compliance_reviewer` 内部交叉校验。

---

## 八、移动端响应式改造（A 方案，2026-08-02 续，commit `cfdf2ad`）

> 触发：杜总问「PC 端应用是否考虑移动端」→ 追溯 `docs/DEPLOYMENT_READINESS.md:60` 既有 P2 规划（企业微信/钉钉小程序 2-3 周）。经三方案评估（A 响应式 / B 小程序 wrapper / C 原生 App），杜总选 A。

### 8.1 现状摸底（改动前实测）

| 项 | 结果 |
|---|---|
| viewport 元标签 | ✅ 已有（`index.html:6`） |
| Tailwind 响应式类 | ✅ 各组件普遍在用（`sm:`/`md:`/`lg:`） |
| 侧栏窄屏抽屉 | ✅ 已有（`hidden lg:flex` 常驻 + `lg:hidden` 抽屉复用 AgentSidebar） |
| **车间工人场景**（DeviceMonitor/AlertPanel）| ✅ 本就响应式（`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`） |
| **顶栏 Tab 条** | ❌ 21 个 Tab 被挤进 ~100px（手机上不可用） |
| **结果视图**（GenericResultView）| ❌ 固定 `grid-cols-3/4`（无断点，手机挤成 ~75px/列） |

### 8.2 修复清单（纯前端、后端零改动）

- **顶栏重构**：`flex-wrap` + `order-{1,2,3}` → 手机端 Tab 条整行落到第 2 行；桌面 `lg:flex-nowrap` 保持三栏（品牌 | Tab 居中 | 右侧）原样。Tab 按钮 `py-2 lg:py-1.5` 加大触控区。
- **根级防护**：根 div `[overflow-x:clip]`（用 `clip` 而非 `hidden`，不破坏 sticky；防手机页面横向滚屏）。
- **非 Studio 主区**：`<main>` 加 `overflow-x-auto` 防宽内容爆屏。
- **结果视图**：`GenericResultView` 全部固定 `grid-cols-3/4` → `grid-cols-2 sm:grid-cols-3/4`（手机 2 列可读）。

### 8.3 验证证据（agent-browser 375px 实拍）

- 核心/边缘双部署 `cfdf2ad`，双入口 smoke PASS。
- 三张 375px 实拍（`.tmp_mobile_shots/`）：`m1_studio_input_375.png`（顶栏双行+北极星双率）、`m2_monitor_375.png`（设备卡纵向堆叠=车间工人场景）、`m3b_caselib_full_375.png`（案例库财报表+推演卡全页）。
- eval 实测：`hasHScroll:false`（无横向滚屏）；财报表 `table.offsetWidth=316 < 375`。
- 登录实证（边缘 curl + 浏览器）：`telecom_admin` / `Zhiyan@telecom_admin2026`（案例租户确定性密码）。

### 8.4 与小程序的关系（递进三阶，杜总定调 2026-08-02）

- **① 手机版 H5（已完成）** → **② 企业微信自建应用 H5（推荐下一步：免登 agentConfig + 工作通知推送，无需代码审核）** → **③ 小程序（最后，有真实需求再上：认证300元+ICP备案+类目+每版代码审核）**。
- ② 是「车间工人收缺料预警」的最优解：企微后台建自建应用 + 可信域名，H5 代码 100% 复用；① 是②的前置。

---

## 九、营销向智能体缺口归因 + customer_voice 客户声音源（2026-08-02，commit `565c905`）

> 触发：杜总问「系统缺乏营销方面智能体，是刻意理解（工业互联网不需要营销）还是其他原因」。经商量确认方案 A（不扩边缘）。

### 9.1 归因结论（诚实四层）

| 归因 | 结论 |
|---|---|
| 战略聚焦（主因） | 北极星=决策实时化率，24 Agent 按产供销命脉排布，营销不在核心闭环——⚠️ 可商量 |
| 数据源约束 | 营销要真有用需 CRM/商机数据，智衍接网关+围墙内 IT——但第⑥路客户声音是**公开数据**（招投标/行业报告/舆情），不受此限 |
| 范围纪律 | 候选池聚焦制造核心、先有后优——✅ 合理 |
| **落地遗漏（最该修的）** | 第⑥路战略定义含「客户声音」，但 `env_sources` 落地只有 policy/market/benchmark/disclosure——**定义了没做**，与目标达成审计「六路感知仅 1.5/6 路产生真信号」同一条线 |

### 9.2 修复内容（方案 A：补全已定义未落地的感知路，不新增 Agent）

- **新增 `src/runtime/env_sources/customer_voice_source.py`**：`kind=customer_voice`，label=「客户声音（招投标/行业报告/舆情）」；**credibility=authoritative → 进人工审核队列**（F4 官方为锚、其余必筛红线，批准后才锚定）；live URL `settings.env_customer_voice_url`；simulated 样本对齐通讯行业客户声音（集采招标/资本开支/交付质量舆情）。
- **`manager.py` 注册**（4→5 源）；`config.py` 加 `env_customer_voice_url`。
- **免费额度 3→4**（`env_subscription_store.py::FREE_MAX_SOURCES`）：customer_voice 是 tenant_facing 源，默认模板 3→4；免费圈=纯⑥信号公开源，客户声音（商机情报）是免费圈钩子，不算破坏免费承诺。
- **前端零改动**（EnvPerceptionPanel 按 `source.label` 动态渲染，新源自动出现）；**外圈 5 Agent**（executive_cockpit/supply_chain/procurement_manage/compliance_q/industry_research）经 `env_context()` 通道级自动消费，零 agent 改动。

### 9.3 验证

- 全量 pytest **567 passed / 0 failed**（248s）；env 30 passed（含 +4 新测试）；订阅 19 passed + 额度 42 passed（断言 3→4 更新）。
- 核心部署 `565c905`；双入口 smoke PASS。
- **线上实证**（telecom_admin）：`/environment` 源清单 5 源在线（customer_voice: kind=customer_voice / cred=authoritative / mode=simulated）；手动 pull 2 条 published 2 条；UNS 通道可见 2 条客户声音信号（集采招标强调低时延与自主可控 / 资本开支回暖），均 `cred=authoritative`。

### 9.4 营销向后续（方案 B 预留，未做）

- 若验证「客户声音公开信号有价值」，可单独立项新增第 25 个 Agent「商机情报 agent（bid_intel）」（标前评审/赢单概率/报价策略）——这属明确扩边缘，需杜总拍板。

---

## 十、商机情报 Agent bid_intel（第 25 个 Agent，2026-08-02，commit `055caa6` + `8f73cc6`）

> 触发：杜总「接受你的建议」拍板方案 B——营销向智能体从「信号补齐」升级为「Agent 实体化」。

### 10.1 设计要点

- **工业 B2B「营销」= 商机情报**（与 C 端增长漏斗不同）：标前评审 / 赢单概率 / 竞品对标 / 报价策略。
- **纯环境信号驱动**：消费第⑥路 `customer_voice` + `benchmark` + `market` 三源（经 `env_context()` 通道级），不依赖租户内部数据 → **归外圈「免费纯⑥信号」**（G 模式语义不变，外圈 4→5）。
- **🔴 人留终审**：`actions_taken` 恒空，不自动执行商务动作；AuthBoundary `auto_execute=[]`，`submit_bid`/`issue_quote` 须审批。
- **赢单概率确定性规则**（非黑盒）：信号强度 40% + 竞争烈度 35% + 成本锚 25%，标注推导依据。
- **research_case 纪律**：不写租户记忆、payload 匿名（`_assert_no_leak` 零真名）。

### 10.2 落地清单

| 层 | 改动 |
|---|---|
| Agent | `src/agents/bid_intel/agent.py`（商机扫描/竞品对标/成本锚/赢单概率/报价策略/标前评审） |
| 路由 | `AGENT_REGISTRY` + `ROUTING_RULES`（专属词投标/标前/赢单/商机/招投标/客户声音；⚠️ 不用「报价」——会被 cost_analysis 先截获） |
| 权限 | `AuthBoundary(ab-bid-intel-default)` + `FINANCE_CONTROLLER` 加 bid_intel（可读）；`PLANT_MANAGER` 全放行自动覆盖 |
| 三圈 | `unlock_map.OUTER_AGENTS` + bid_intel（外圈 4→5） |
| 前端 | `SCENARIO_GROUPS`（经营决策组）+ `DEFAULT_EXAMPLES` + `AGENT_META`（🎯 商机情报）+ 结果分支白名单 |

### 10.3 验证

- bid_intel 专项 **11 passed**（注册/路由/功能/人留终审/research_case 纪律/权限边界/不抢报价）。
- 全量回归 **578 passed / 0 failed**（244s，含 24→25 计数连锁修复：registry/onboarding/compliance/unlock 四文件）。
- tsc 0 错误；vite build 水印 `8f73cc6` 正确（白屏防御标记在）。
- 核心 `8f73cc6` 部署 + 边缘 release=`8f73cc6`；双入口 smoke PASS。
- **线上端到端实证**（telecom_admin）：
  - `quick-check("评估运营商集采项目的投标赢单概率与标前评审")` → `routed_agent=bid_intel`，赢单概率 89（高）
  - 先拉取 `customer_voice`(3)+`benchmark`(2) 入 UNS → bid_intel 真实捕获 **3 个商机机会**（「某运营商发布新一轮集采招标：强调低时延与自主可控」）+ **2 条竞品对标**，`env_signal_count=5`
  - `actions_taken=[]`（🔴 人留终审生效：情报分析不自动执行商务动作）
  - 无信号时诚实输出「捕获 0 个商机信号」而非编造（事实锚点铁律）

---

## 十一、移动端第②阶骨架 + 数据源接入指南（2026-08-02，commit `15fd550`）

> 触发：杜总确认两项推进方式——①招投标数据源**先出接入指南**；②企微自建应用**写骨架+操作清单**。

### 11.1 企微自建应用 H5 骨架（代码已就绪，配凭证即用）

- `src/runtime/wecom/service.py`：`get_access_token`（缓存）/ `get_jsapi_ticket`（缓存）/ `sign_agent_config`（agentConfig 签名 sha1）/ `send_app_message`（textcard 应用消息推送）。
- `src/runtime/api/wecom.py`：`GET /wecom/status`、`POST /wecom/jsapi-signature`、`POST /wecom/push`（JWT 门禁；未配置 503 提示）。
- `config.py` +4 配置项（`wecom_corpid/secret/agentid/token`，env_prefix `zhiyan_`）。
- 🔴 **优雅降级**：凭证缺失时全部返回 None/降级 dict，绝不抛异常、绝不阻塞平台（现状即未配置态，线上零影响）。
- 🔴 **凭证铁律**：Secret 只进服务器 `.env`，status() 明文脱敏。
- 操作清单 `docs/WECOM_ONBOARDING_GUIDE.md`（6 步：建应用→可信域名校验→网页授权→CorpID→.env→验证）。
- 缺料推送接线点：`supply_chain` 缺料检测分支调 `send_app_message`——**凭证到位后动工**（第二阶段）。

### 11.2 招投标数据源接入指南（代码已就绪，缺凭证）

- 代码：`customer_voice_source._live_url()` 读 `env_customer_voice_url`，`_parse_live()` 已实现 live 解析（JSON 数组约定），失败自动回退 simulated。
- 指南 `docs/ENV_DATA_SOURCE_GUIDE.md`：URL 格式约定 + 🔴 合规红线（不爬未授权站点/密钥只进 .env）+ 服务商类型参考 + 接入步骤 + 回退运维。
- 接入后 `customer_voice` 升级 live → `authoritative` 人工审核队列 → bid_intel 自动消费（零改动）。

### 11.3 验证

- wecom 专项 **8 passed**（未配置降级/token 缓存/签名确定性/push payload/API 503）。
- 全量回归 **586 passed / 0 failed**（578 + 8 新 wecom）。
- 核心部署 `6fed8bc`；双入口 smoke PASS。
- **线上实证**（telecom_admin）：`GET /wecom/status` → `configured:false` / `mode:unconfigured` / 三凭证位全 false（优雅降级零影响）；`POST /wecom/jsapi-signature` → **503**（未配置拒绝，符合预期）。

---

## 十二、前后台分面：角色化 Tab 过滤（2026-08-02，commit `4d735ce`）

> 触发：杜总问「是否有前后台」→ 实答单体 SPA 无物理前后台（Tab 条此前全可见）→ 杜总确认做角色化 Tab 过滤。

### 12.1 现状（改动前）

- 单体前端（`studio/` React SPA）+ 单后端（FastAPI），无独立前台/后台站点。
- 「一人一面」此前只体现在 **Agent 侧栏**（`capability_scope` 按业务岗位过滤）；**Tab 条 20/21 全可见**（仅 permission 条件渲染）——普通员工能看到审计/租户/网关等管理 Tab。

### 12.2 修复（纯前端、架构零改动）

- `ADMIN_ONLY_TABS`（13 管理类）：console/audit/strategy/governance/federation/supplychain/gateway/twin/writeback/tenant/connect/knowledge/permission → 仅 `tenant_admin/superadmin` 可见。
- 业务用户（车间/工艺/质量/供应链/财务/厂长岗位）见 **8 个业务 Tab**：studio/monitor/tacit/bluearc/history/symbiosis/caselib/presetlib。
- `effectiveTab` 兜底：业务用户 state 落管理 Tab（直连/降权）显示回退 studio；setTab 不受影响（业务用户点不到管理 Tab）。
- permission Tab 并入统一过滤（去掉原独立条件渲染）。

### 12.3 验证

- tsc 0 错误；vite build 水印 `4d735ce`（白屏防御标记在）。
- 核心 `4d735ce` 部署 + 边缘 release=`4d735ce`；双入口 smoke PASS。
- agent-browser admin 实拍：**21 Tab 全可见**（含用户权限）无回归。
- ⚠️ 业务用户视角未经真实账号实测（避免污染生产数据）——filter 逻辑经 tsc + 代码审查；可在「用户权限」建测试岗位账号实证。

---

## 十三、半年复盘 + Agent 心跳自触发（2026-08-02，commit `3540cd2`）

> 触发：杜总「总结近半年经验教训，先讨论方案再动手」→ OpenClaw（小龙虾）架构讨论后拍板借鉴 HEARTBEAT 模式，实现「从被动应答到主动巡检」。

### 13.1 半年复盘（docs/HALF_YEAR_RETROSPECTIVE_2026-08-02.md，15 条）

- 战略：路线 A 定调终结讨论期；研究案例范式（不等客户）；先有后优范围纪律。
- 教训：工程自嗨陷阱（08-01 审计：工程✅业务❌，真实决策实时化率=0%）；事实锚点铁律。
- 架构：通道级消费=零改动扩展；韧性降级全栈铁律。
- 安全：GH013 凭证教训；企微/数据源凭证只进 .env。
- 工程：全量回归连锁断言；白屏三层防御；vite 构建顺序；沙箱坑。
- 产品：移动端三阶；前后台分面。
- **缺口：Agent 全部被动（人提问才动）——北极星名不副实，是「演示系统」到「决策系统」的分水岭。**

### 13.2 心跳自触发（方案 → 落地，杜总拍板：默认关/复用现有告警/全量实施）

- `src/runtime/heartbeat/engine.py`：HeartbeatEngine（async 调度器，per-agent 频率；静默门控=无风险不产生告警；幂等=复用 AlertMonitor cooldown 300s 去重；统计端点）。
- 巡检复用 `analyze(mode="heartbeat")`，**0 新 Agent**：
  - supply_chain：缺料风险扫描（不 execute，无锁料/补货副作用）
  - bid_intel：商机信号扫描（本就无副作用）
  - energy_carbon：碳强度/绿电异常（非 tenant 不创建节能任务）
- 风险告警复用 `AlertMonitor._fire`（UNS system 路 + /monitoring/alerts + AlertPanel，**零新端点零新界面**）；企微凭证到位接 /wecom/push。
- 默认关闭 `ZHIYAN_HEARTBEAT_ENABLED=1` 开启（先有后优）。
- 🔴 韧性：单次巡检失败静默；heartbeat 不写租户记忆（视同 research_case 纪律）。

### 13.3 验证

- 心跳专项 **11 passed**（风险判定/静默门控/幂等去重/无副作用/不污染租户）；bid_intel+supply_chain 13 passed。
- 全量回归 **597 passed / 0 failed**（261s，586 + 11 新心跳）。
- 核心部署 `0887a8d`；双入口 smoke PASS（默认关闭 ZHIYAN_HEARTBEAT_ENABLED 未开，平台零影响）。
- **主动巡检实证**（本地真实跑 patrol_once）：
  - supply_chain 心跳：SMIC seed 自动检出 **7 项缺料风险** → `fired:true` → 发布 critical 告警「[心跳·缺料巡检] 缺料风险项 7 项」进告警缓冲（前端 AlertPanel 同源展示）
  - bid_intel 心跳：无商机信号 → `fired:false` **静默**（静默门控生效，不打扰）
  - 引擎统计：runs=2 / alerts=1 / enabled=false（默认关）

---

## 十四、财务决策维度补全（2026-08-02，commit `12c06ab`）

> 触发：杜总问「HR/财务智能体没有，如何考虑」→ 核查归因 → 杜总「听你的建议」执行 A（零扩边缘），B 单独立项暂缓。

### 14.1 现状与归因（代码实证）

- 财务**半覆盖**：executive_cockpit（经营 KPI/损益/现金流/预算）+ cost_analysis（制造成本）——管理会计有，财务会计（应收/应付/税务/资金预测）无。
- HR **零覆盖**：26 模块无任何 HR Agent；③路人感知（CHANNEL_HUMAN）已落地可衔接。
- 归因：战略聚焦（北极星产供销核心）+ 🔴 **账本类归 ERP**（路线 A 非原生账本红线）+ 数据源未接。
- 判断：补「决策层」不补「账本/系统」——财务=现金流预测+应收风险（不是记账）；HR=人效+人员风险（不是招聘考勤系统）。

### 14.2 修复（A：executive_cockpit 财务决策，零扩边缘）

- `tools.py`：应收账龄 seed（4 分桶）+ `get_receivables()`（90+逾期占比/风险级）+ `cash_forecast()`（3 月滚动：现金+回款流入−运营支出，确定性规则）。
- `agent.py`：tenant 模式加 `financial_decision` 块（receivables+cash_forecast）；`mode=heartbeat` 分支（只推演不执行 create_action_item）。
- 心跳第 4 个巡检「资金巡检」（executive_cockpit，12h）：现金安全垫<30 天 / 90+应收≥15% / 预测现金≤0 → critical 告警。
- 🔴 战略红线：只读推演（决策），账本归 ERP 不在此层。

### 14.3 验证

- 心跳专项 **15 passed**（+4：财务字段/心跳无副作用/资金风险判定/资金巡检静默）。
- 全量回归 **601 passed / 0 failed**（597 + 4）。
- 核心部署 `12c06ab`；双入口 smoke PASS。
- **实证**：tenant 模式输出应收总额 6100 万 / 90+逾期 9.8%（medium）/ 3 月预测最低现金 2292 万（充足）；资金心跳当前无风险 → 静默。

### 14.4 HR（B：hr_intel）单独立项暂缓

- 形态=人力效能+人员风险（人效/关键岗位依赖/技能断层/人员风险预警），衔接③路人感知。
- 🔴 数据源依赖 HR 系统接入——现在做是空壳；等有 HR 数据源再立项（骨架可先行）。

---

## 十五、北极星主动决策实时化率子指标（2026-08-02，commit `d8623ff`）

> 「继续」：把 OpenClaw 心跳借鉴成果**锚定进北极星**——北极星从「被动实时化率」升级为「被动+主动」双口径。

### 15.1 改动

- `metrics.py::north_star_report()` 新增：
  - `proactive_decision_count`：心跳主动检出的风险告警数（heartbeat_engine.stats()["alerts"]）
  - `proactive_decision_rate`：心跳告警 ÷ (决策事件 + 心跳告警)——「系统主动发现并推达」占全部决策触达的比例
  - `proactive_source`：诚实标注「当前 seed 演示态，真实源接入后自动升级」
- 事实锚点：无心跳告警时 count=0/rate=None 或 0（0 触达不虚报）。

### 15.2 验证

- 测试 +2（维度存在 / 率=3÷(12+3)=0.2）；dute+heartbeat 20 passed。
- 全量回归 **603 passed / 0 failed**（601 + 2）。
- 核心部署 `d8623ff`；双入口 smoke PASS。
- **线上实证**：`/reports/north-star` 返回 `decision_realization_rate_real=1.0`(12 真实)、`proactive_decision_count=0`、`proactive_decision_rate=0.0`（心跳默认关，纯被动诚实呈现）、`proactive_source=heartbeat（当前 seed 演示态…）`。
- 意义：开启 `ZHIYAN_HEARTBEAT_ENABLED=1` 后，心跳每检出一次风险告警，主动决策率随之起跳——北极星首次能区分「人问出来的决策」和「系统自己发现的决策」。
