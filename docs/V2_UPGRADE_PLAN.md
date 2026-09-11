# 智衍 EvolvIQ 第二版升级计划（V2 Multi-Industry Combat Edition）

> 文档性质：架构与功能审计 + 升级路线图（含愿景主线决策定稿）
> 触发背景：进入实战阶段，将新增不同行业与企业；第一版（V1）以"半导体为默认、沪东造船为特例修补"的方式验证，已无法支撑规模化多行业。
> 审计依据：直接读取 `src/runtime`、`src/agents`、`studio/src`、`docker-compose.prod.yml` 实际代码（非凭记忆）。
> 审计日期：2026-09-12
> 决策定稿：2026-09-12（愿景主线纳入，首日 L1+L2）

---

## 0. 一句话结论

V1 把"行业"当成**代码里的枚举 + 硬编码覆盖字典 + 写死在 Agent 脑子里的术语**。要新增一个行业，今天需要改 `enterprise_store.py`、`equipment_profiles.py`、`agents_api.py`、`router.py` 四处代码，且 Agent 真正生成内容时仍满嘴"晶圆/SMT"。V2 的目标是：**行业成为数据驱动的一等公民（一个 manifest 文件即可上架一个行业），所有租户领域数据持久化到数据库，Agent 内容按行业自适应，并支持客户自助注册 + 自动识别行业**。

---

## 0.5 愿景主线决策（2026-09-12 定稿）

> 决策背景：用户希望"客户注册后提供公司名称 + 官网 + 微信公众号，系统自动识别行业并建立企业个性化智能体体系"，以降低行业推广难度。该愿景将 V2 从"内部运营工具"升级为"自助 SaaS 平台"。

**已定方向：纳入愿景主线，首日覆盖 L1+L2 档。**

- **L1（注册 + 人确认行业 + 行业模板个性化）**：注册填行业（下拉从 manifest 读），选行业即自动套用该行业 Agent 套件 + 设备库 + 路由词。个性化 = 行业模板级。
- **L2（自动识别行业 + 人确认）**：LLM 读公司名 + 官网首页文本（httpx 抓取，SSR 可抓）+ 公众号（**首日降级为"客户主动粘贴文章/简介"**，不主动爬） → 分类到 manifest 行业树 + 置信度，低置信度落「通用制造」兜底。识别非 100% 准，必须保留"人确认关卡"。
- **L3（企业级知识自举，官网抓取 → 抽取 → 进知识库 → 注入）**：技术可行但有三道坎（公众号合规 / 识别准确率 / 知识反幻觉红线），**列为 V2.5 增强**，非首日必交付，避免为"全自动"牺牲准确性砸招牌。

**对架构的新增要求**（叠在原 P0/P1/P2 骨架上）：

- 新增 **P1.5 行业识别 + 自助注册**：注册表单加官网/公众号字段 + `IndustryResolver`（LLM 分类服务）+ 人确认 UI。
- 原 P3（自助开通）升级为**面向客户的注册**（非仅超管脚本）。
- 新增 **P2.5 企业知识自举**（L3 预留，V2.5）。

**三道坎护栏（写入设计纪律）**：① 公众号首日不主动抓，改客户粘贴；② 行业识别必须有人确认关卡，不允许全自动落库；③ 任何企业级知识注入须"引用来源 + 人审"，反幻觉红线不破。

---

## 1. 现状审计（V1 的真实问题）

### 1.1 行业（industry）根本不是一等概念

| # | 事实 | 位置 | 后果 |
|---|------|------|------|
| A1 | `Tenant` 模型**没有 `industry` 字段**，只有 id/name/api_key/is_active/gateway_config | `src/runtime/models/tenant.py:33-52` | 行业无法随租户进入鉴权/路由主干 |
| A2 | 行业实际存在**企业画像 JSON** 里（`profile_store[tenant_id]["industry"]`），而该 JSON 是容器本地文件 | `src/runtime/enterprise_store.py:48-71` | 见 1.3 持久化缺陷 |
| A3 | 行业是一个**封闭枚举**，写死 8 个值 | `src/runtime/enterprise_store.py:32` `PROFILE_INDUSTRIES = ["半导体","3C","新能源汽车","通讯","光伏","工程机械","造船","其他"]` | 加行业必须改代码 |
| A4 | Agent 名称/描述覆盖是**写死的字典**，目前只覆盖"造船"一个行业 | `src/runtime/api/agents_api.py:236-280` `INDUSTRY_AGENT_OVERRIDES` | 加第 3 个行业 = 再塞一个硬编码块，不可扩展 |
| A5 | 路由触发词（router）把"SMT/晶圆/光刻/AOI"与"分段装配/船级社"混在一起硬编码 | `src/runtime/agent/router.py` | 行业一多，触发词冲突、误路由必然发生 |

### 1.2 Agent "脑子"里全是半导体（最深的坑）

- 仅 Agent **元数据**（名称/描述/场景）被覆盖层处理；**Agent 实际生成内容时调用的 `analyze()`/`prompts.py`/`tools.py` 仍写死半导体术语**。
- 全量扫描：`src/agents/` 下 **39 个文件** 含 `晶圆|半导体|芯片|wafer|smt|AOI|光刻|良率` 等硬编码。
- 含义：沪东造船用户点开"新船型导入 Agent"，底层仍按"NPI/晶圆试产"逻辑作答。**名称换了，脑子没换**——这正是你截图里"做的是造船的事、用的是半导体名字"的根因（名称覆盖是 V1.5 刚打的，内容层还没动）。

### 1.3 持久化架构分裂，重建即丢（生产级阻断）

| 数据 | 存储位置 | 是否随 `docker compose up -d runtime` 重建存活 |
|------|----------|----------------------------------------------|
| 租户 / 账号鉴权 | Postgres（`Tenant` 模型） | ✅ 存活 |
| 企业画像（含 industry） | 容器本地 `data/enterprise_profiles.json` | ❌ **丢失** |
| 凭证 Vault | 容器本地加密 JSON | ❌ 丢失 |
| 普通业务用户库 | 内存 | ❌ 丢失 |
| UNS 事件流 | 内存 deque | ❌ 丢失 |
| 环境感知信号 | 内存 | ❌ 丢失 |

证据：`docker-compose.prod.yml:181-183` 只有 `pgdata`/`neodata` 两个命名卷，**runtime 容器没有挂 `data/` 卷**。因此每次重建 runtime，必须靠 `prep_hudong_demo.py` 手动回灌——对单演示租户可接受，对"加不同行业和企业"等于每加一家都要人工脚本兜底。

### 1.4 已具备的好地基（V2 要保留并放大）

- ✅ 权限作用域**已经行业感知**：`scope_for_business_role(role, industry=...)`（`src/runtime/authn/`），新租户可按行业拿不同能力集。
- ✅ `/authn/my-agents` 已按 `tenant_id → profile.industry` **实时**计算覆盖（`src/runtime/authn/api.py:217-232`），切租户即换名；前端 `App.tsx` 的加载已 gate 在 `activeTenant?.tenant_id` 上。
- ✅ 存在**数据驱动种子框架** `src/runtime/seed/__init__.py`（`load_industry_seed` / `bootstrap_industry`），但 `data/seed/<industry>/seed.json` 目录**为空**，框架是 stub，未接线。
- ✅ 设备库已按行业分 key（`INDUSTRY_EQUIPMENT_TYPES`），只是新增要改代码。
- ✅ LLM 客户端已具备（`src/common/llm_client.py`，httpx 直连 OpenAI 兼容协议）—— `IndustryResolver` 可直接复用。
- ✅ 知识图谱已按 `industry_key` 组织（`src/knowledge_graph/`），行业隔离纪律已就位。

### 1.5 真实场景复盘（你提到的"性质变化名称没跟"）

- V1 早期：`/authn/my-agents` 不读 industry → 沪东显示半导体 Agent 名（你看到的那张图）。
- 现已修复（V1.5）：后端实时覆盖 + 前端按 tenant 重拉；名称已随行业变化。
- **残留缝隙**：同一租户在后台把"性质"改了（industry 字段 in-place 编辑），前端若不重新拉取（重新登录/重挂载）不会自动刷新。需在 V2 把"industry 变更"纳入前端重拉触发条件（见阶段 4）。

---

## 2. V2 目标架构

### 2.1 设计原则

1. **行业 = 数据，不是代码**。一个 manifest 上架一个行业，零代码改动。
2. **租户领域数据 100% 持久化**。画像/行业/凭证/用户/事件全部进 DB 或卷挂载，重建不丢。
3. **Agent 内容按行业自适应**。提示词模板化 + 行业知识包按会话注入，告别 39 文件硬编码。
4. **自助开通主线**。注册即提供公司名/官网/公众号 → `IndustryResolver` 自动识别行业 → 人确认 → 一键套用 manifest + 开通。
5. **保留铁律**：零真名、配额、凭证隔离、capability_scope 行业感知、三道坎护栏——全部继承。

### 2.2 目标组件图

```
                ┌─────────────────────────────────────────────┐
                │            Industry Manifest Registry         │
                │  (DB 表 industry_manifests，或卷挂 JSON)       │
                │  每个行业一个 manifest：                        │
                │   { key, label, agent_overrides,              │
                │     router_triggers+, equipment_types,       │
                │     knowledge_pack, sample_seed }            │
                └───────────────┬─────────────────────────────┘
                                │ 读取
        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                          ▼
  Tenant(加industry列)   Agent Overlay 引擎        Agent 内容层
  (Postgres)            (读 manifest，不再硬编码)  (模板+知识包注入)
        │                                                │
        ▼                                                ▼
  EnterpriseProfile(进DB)                       39个 agent.py 改为
  CredentialVault(进DB/卷)                       {{industry_context}} 插槽
        │
        ▼
  IndustryResolver (L2新增)  ← 客户注册填官网/公众号
   (抓取+LLM分类+置信度+兜底) → 人确认关卡 → provision_industry()
        │
        ▼
  TenantBootstrap (开通即注入设备/样本/事件 + 企业知识库)
```

---

## 3. 升级路线图（六阶段，按阻断级排序）

### 阶段 0 — 持久化止血（最高优先级，1~2 天）
**目标：加企业不再需要人工 prep 脚本；重建容器数据不丢。**

- [ ] `Tenant` 模型新增 `industry` 列（`models/tenant.py`），行业成为租户原生属性，写入 Postgres。
- [ ] `EnterpriseProfileStore` 改为 **DB 后端**（新建 `enterprise_profiles` 表 + `credential_vault` 表），废弃本地 JSON；保留"落盘失败降级内存"的韧性但默认走 DB。
- [ ] 普通业务用户库改为 Postgres 持久（现有内存 `user_store` 迁移）。
- [ ] UNS 事件流：短期用**命名卷**挂 `/data/uns` 做冷持久；长期并入 Postgres/Neo4j 事件表。环境感知信号同。
- [ ] 删除对 `prep_hudong_demo.py` 的依赖，改为幂等 provisioning 服务。
- **验收**：`docker compose up -d runtime` 后，既有租户画像/用户/凭证/事件自动恢复，无需脚本回灌。

### 阶段 1 — 行业 Manifest 框架（核心解耦，2~3 天）
**目标：加一个行业 = 放一个 manifest 文件，零代码改动。**

- [ ] 定义 `IndustryManifest` 数据模型（Pydantic），字段含：
  - `key` / `label`
  - `agent_overrides`：取代 `INDUSTRY_AGENT_OVERRIDES` 硬编码字典
  - `router_triggers_extra`：行业专属触发词（追加，不污染通用词）
  - `equipment_types`：取代 `INDUSTRY_EQUIPMENT_TYPES` 代码 dict
  - `knowledge_pack`：指向行业知识包（见阶段 2）
  - `sample_seed`：样本数据引用
- [ ] `enterprise_store.PROFILE_INDUSTRIES` 改为**从 manifest 注册表动态派生**（开放枚举）。
- [ ] `agents_api._apply_industry_overlay` 改为读 manifest，删掉硬编码 `INDUSTRY_AGENT_OVERRIDES`。
- [ ] `equipment_profiles.INDUSTRY_EQUIPMENT_TYPES` 改为读 manifest（保留向后兼容的 fallback）。
- [ ] 把现有"半导体""造船"落地为两个 manifest 文件，验证零回归。
- **验收**：新增 `data/industries/新能源电池.json` 即可让该行业上架，无需改任何 `.py`。

### 阶段 1.5 — 行业识别 + 自助注册（愿景主线，2~3 天）【新增】
**目标：客户自助注册，填官网/公众号，系统自动识别行业并套用模板，人确认后落地。**

- [ ] **注册表单改造**：公司名 + 官网 URL + 微信公众号（或粘贴文章）字段；行业下拉从 manifest 注册表动态读取（前端 `EnterpriseOnboardingPanel` 已留"造船"位，改为动态）。
- [ ] **`IndustryResolver` 服务**（后端新增 `src/runtime/industry_resolver.py`）：
  - 官网抓取：httpx 抓首页文本（**超时 / 域名白名单 / 沙箱**，防恶意站与无限等待）。
  - 公众号：**首日不主动抓取**，接收"客户粘贴的文章文本/简介"作为输入之一（护栏坎1）。
  - LLM 分类：公司名 + 官网文本 + 公众号文本 → 输出 `{industry_key, confidence, reasons}`，候选命中 manifest 行业树。
  - 兜底：confidence < 阈值 或 无命中 → 落「通用制造」模板，并提示"可联系我们定制行业"。
- [ ] **人确认关卡**：识别结果呈现给用户/超管，允许改行业，确认后才写 `Tenant.industry` + 触发 manifest 套用（护栏坎2：不允许全自动落库）。
- [ ] 触发链：复用阶段 3 的 `provision_industry(tenant, industry_key)`，注册即建全套。
- **验收**：一家新企业注册填官网，系统推荐行业并人确认后，立即看到该行业 Agent 套件 + 设备库，无需任何人工脚本。

### 阶段 2 — Agent 内容行业自适应（最深一公里，3~5 天）
**目标：点开"新船型导入"，回答也是造船语境，而非晶圆 NPI。**

- [ ] 把 `src/agents/*/agent.py` 与 `prompts.py` 中写死的半导体术语改为**模板插槽** `{{industry_context}}` + `{{equipment_terms}}`。
- [ ] 用阶段 1 的 `knowledge_pack` 机制：每个行业一份知识包（术语表、典型设备/工艺、指标口径、合规框架），会话级注入 Agent system prompt。
- [ ] 复用并接线已存在的 `src/runtime/seed/__init__.py`：把空 `data/seed/<industry>/seed.json` 填充为"行业事实 + 样本事件"，`bootstrap_industry` 改为**按租户按需触发**（非全局 env）。
- [ ] 路由层：通用触发词（"排程/成本/质量"）保留；行业专属词从 manifest 注入，避免 A5 的冲突。
- **验收**：对同一目标，半导体租户与造船租户拿到**内容口径不同**的回答（非仅名称不同）。

### 阶段 2.5 — 企业知识自举（L3 预留，V2.5，2~3 天）【新增，非首日】
**目标：从企业官网抽取结构化知识注入租户知识库，做到企业级个性。**

- [ ] 官网深度抓取 + 文本抽取（产品/工艺/组织/指标），结构化进租户知识库（依赖阶段 0 持久化）。
- [ ] 会话级注入 Agent system prompt，带"引用来源"标签。
- [ ] 反幻觉护栏（坎3）：知识须人审后才进生产；未审知识标注"待确认"，Agent 引用时显式提示。
- [ ] 公众号主动抓取视平台合规进展决定；首日不阻塞。
- **验收**：企业官网的产品/工艺术语出现在该租户 Agent 回答中，且每条断言可溯源到抓取来源。

### 阶段 3 — 自助开通与租户管理（运营闭环，2~3 天）
**目标：客户/超管自己开通新行业企业，无需脚本。**

- [ ] `POST /admin/provision`（及阶段 1.5 的客户自注册端点）：入参 `(tenant_name, industry_key, admin_user[, website, wechat])` → 建租户 + 设 industry + 注入设备模板 + 种子样本 UNS/环境 + 应用 manifest 覆盖 + （可选）跑 IndustryResolver。
- [ ] 租户密钥管理 UI：生成/轮换 X-Tenant-Key（沿用现有 `gen_key`/`hash_key`）。
- [ ] 入驻行业下拉从 manifest 注册表读取。
- [ ] 清理重复租户（如 `aeqDibWYFZ7l`）的回收工具。
- **验收**：客户在界面上 3 步开一家新行业企业，刷新即见该行业全套 Agent + 设备。

### 阶段 4 — 前端全响应式 & 多行业演示数据（收尾，1~2 天）
- [ ] 把"industry 变更"纳入 `App.tsx` 重拉触发（修复 1.5 残留缝）。
- [ ] 案例库（`CaseLibraryPanel`）行业筛选/色条已部分支持，补全动态 manifest 色板。
- [ ] 追溯单位（`TraceResultView`）已动态，扩展为 manifest 驱动的 `unit_map`。
- [ ] 每行业一套演示样本数据（设备/事件/案例），便于现场切换演示。

---

## 4. 工作量与依赖

| 阶段 | 估时 | 前置 | 阻断级 |
|------|------|------|--------|
| P0 持久化止血 | 1~2 天 | 无 | 🔴 阻断（不加则规模化无从谈起） |
| P1 Manifest 框架 | 2~3 天 | P0 | 🔴 阻断（不加则加行业必改码） |
| P1.5 行业识别+自助注册 | 2~3 天 | P1 | 🔴 主线（愿景核心交付） |
| P2 内容自适应 | 3~5 天 | P1 | 🟠 高（决定"像不像该行业"） |
| P2.5 企业知识自举 | 2~3 天 | P0+P1 | 🟡 V2.5（非首日） |
| P3 自助开通 | 2~3 天 | P0+P1+P1.5 | 🟠 高 |
| P4 前端收尾 | 1~2 天 | P1 | 🟡 中 |

**建议顺序**：P0 → P1 → P1.5 → (P3 并行) → P2 → P4 → P2.5（V2.5 单独排期）。
P2 最重但可分期（先覆盖 top-5 高频 Agent：supply_chain / pm_maintenance / cost_analysis / yield_analysis / executive_cockpit）。

---

## 5. 风险与待你拍板的点

1. **是否先 P0 再对外演示？** 当前 43 演示环境靠手动 prep 脚本维持，P0 完成前不建议在演示机上频繁重建容器。
2. **行业知识包的内容来源**：V2 需要每个行业一份"术语/工艺/指标/合规"知识包。可由你提供行业资料，或我先搭空模板 + 沪东/半导体两例，后续填充。
3. **零真名铁律在内容自适应下如何保持**：知识包与样本数据均须匿名/声明式，V2 的 manifest 与知识包走 `mode:research_case` 纪律，不落真名。
4. **equipment_types 是否并入 manifest**：建议是——设备库与行业强绑定，放进 manifest 最干净。
5. **UNS 持久化取舍**：短期卷挂够用；若要多实例部署需进 DB，待 P0 评估。
6. **公众号抓取护栏（已定）**：首日不主动抓取微信，改"客户粘贴文章/简介"，规避平台合规风险，待评估合规后再考虑主动抓取（阶段 2.5）。
7. **行业识别准确率**：非 100%，必须保留人确认关卡，不允许全自动落库；长尾行业落「通用制造」兜底而非硬猜。

---

## 6. 立即可做的下一步（最小可落地）

若想先验证"自助开通"闭环而不动持久化，可先做 **P1 + P1.5 的轻量串联版**：
- 把 `INDUSTRY_AGENT_OVERRIDES` + `INDUSTRY_EQUIPMENT_TYPES` + `PROFILE_INDUSTRIES` 三处合并为一个 `data/industries/<key>.json` 加载器（不动持久化、不动 Agent 内容）。
- 新增 `IndustryResolver`：抓官网 + LLM 分类 + 人确认，落 `Tenant.industry`（先存本地 JSON 或内存，P0 时再迁 DB）。
- 这样"客户注册填官网 → 自动选行业 → 看到该行业 Agent 套件"可在 1 周内闭环演示，用 30% 的工拿到 70% 的愿景价值。

> 方向已定（纳入 L1+L2）。等你确认 **从 P0 持久化起步** 还是 **先做 P1+P1.5 轻量闭环演示**，我再进入执行。
