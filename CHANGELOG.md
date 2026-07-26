# Changelog

## v28.2 (2026-07-27) — 投产加固：认证持久化修复 + 全局鉴权门禁 + ERP/MES 回写审计桥

### 1. 认证持久化修复（生产 bug）
- 修复 `AuthnService._upsert_db` 漏导入 `select` 导致每次落库抛 `name 'select' is not defined` 被吞、**users 表恒空、管理员仅走内存态**的真实 bug（生产重启即丢账号）。
- `ensure_admin` 拆分为幂等播种 + 启动期专用 `sync_admin_password()`：仅 lifespan 按 `ZHIYAN_ADMIN_PASSWORD` 同步密码，不再经 `authenticate()` 触发，避免覆盖测试 fixture 密码。

### 2. 全局 JWT 鉴权门禁（可配置强制）
- 新增 `require_auth` 依赖：`ZHIYAN_AUTH_REQUIRE=1` 时强制所有受保护路由须持 Bearer JWT（缺失/无效 → 401/403）；未开启时返回匿名上下文，**兼容 150+ 既有测试与不带 token 的 e2e 脚本**。
- main.py 除 `/health` 与 `/authn/*`（登录）外，全部路由挂 `dependencies=[Depends(require_auth)]`。
- 生产 `install.sh`/部署脚本注入 `ZHIYAN_AUTH_REQUIRE=1`。

### 3. ERP/MES 回写审计桥（原生赋能者定位）
- `src/runtime/data_sources/connectors/domain.py`：`RestConnector` 加 `_post` 写方法；MES/ERP 加 `post_audit_record()`。
- `src/runtime/data_sources/writeback.py`：`WritebackBridge` —— agent 决策/审批结论作为**审计记录**回写业务系统（不推倒账本）；连接器不可用/写失败 → 进本地 pending 队列，`retry_pending()` 周期重试；全失败不阻断主流程。
- API：`POST /api/writeback`、`GET /api/writeback/pending`、`POST /api/writeback/retry`、`GET /api/writeback/stats`（均受门禁保护）。

## v28.0 (2026-07-27) — 投产就绪三件套（企业认证 / 一键部署 / 行业知识库）

补齐客户说"我们要用"时最卡脖子的三项（DEPLOYMENT_GAP_ACTION.md P0 + 行业模板）：

### 1. 企业级认证（LDAP/OAuth2/JWT/RBAC）
- **新包 `src/runtime/authn/`**：用户/角色/租户三层 + JWT(HS256,无外部依赖) + RBAC。
- **认证后端**：本地账号（PBKDF2 哈希）+ LDAP/AD（python-ldap 惰性导入，未装则优雅降级）+ LDAP Mock（离线演示）+ OAuth2/OIDC（Azure AD/企业微信/飞书/Keycloak）+ SAML 占位（可插拔）。
- **登录链路韧性降级**：本地 → 目录后端 → 失败；目录用户首登自动建号。
- **API**：`POST /authn/login`、`GET /authn/me`、`GET /authn/backends`、`GET/POST /authn/users`、`POST /authn/users/{id}/role`、`GET /authn/oauth/{login,callback}`。
- **RBAC**：viewer < operator < tenant_admin < superadmin；`get_current_user` / `require_role()` 依赖已就绪，受保护路由可直接挂载。
- **与多租户正交**：JWT 是「用户身份」层，X-Tenant-Key 是「租户」层，互不冲突。

### 2. 一键部署脚本（install.sh + 自动 TLS）
- **`install.sh`**：检测 Docker/端口 → 交互式配置（域名/管理员/DB/LLM）→ 自动生成强随机密钥 → 可选 HTTPS（Caddy 自动 ACME）→ `docker compose up -d` → 输出访问地址与密码。
- **`docker-compose.tls.yml` + `Caddyfile`**：TLS 叠加层，启用后由 Caddy 前置自动证书，studio 不再直出 3006。
- **`bash -n` 语法校验通过**；非交互模式（`--non-interactive` / `--with-tls`）支持环境变量驱动。

### 3. 行业知识库模板（船舶 / 铁路 / 电子）
- **`data/seed/{shipbuilding,railway,electronics}/seed.json`**：各领域 KG 事实 / 本体扩展 / 隐性经验 / Demo 数据。
- **`src/runtime/seed/` 加载器**：`bootstrap_industry(industry)` 按 `ZHIYAN_INDUSTRY` 把种子注入三大回路——KG 事实提议池、本体扩展提议门、UNS human 通道（真实隐性捕获管线，抽取即锚定）。
- 注入均为「提议」待审批门/蓝弧闭环把关，符合事实锚点铁律；任一环失败静默降级。

### 测试与构建
- 新增 `tests/test_authn.py`（9）+ `tests/test_seed.py`（4），`scripts/verify_seed.py` 验证三行业注入。
- 全量回归 **161 passed 零回归**（原 150 + 11 新增）；Vite 构建通过。
- `.env.example` 增补认证/目录对接/行业/TLS 配置项。

## v27.0 (2026-07-26) — Supply Chain Agent Federation

Cross-enterprise supply chain collaboration: share goals, aggregate risks, joint planning across enterprises.

- **Supply chain federation** `src/runtime/federation/supply_chain_federation.py`: `FederatedSupplyChain` — share goals (anonymized), join goals, report/aggregate supply chain risks across tenants, create joint plans.
- **Anonymization**: enterprise IDs masked (企业XXX**), materials de-identified, no prices/contracts exposed.
- **8 new API endpoints**: `POST /federation/supply-chain/goal|risk|plan`, `GET .../goals|risks|plans|fed-status`, `POST .../goal/{id}/join`.
- **SupplyChainFederation.tsx**: 4-tab UI panel (goals/risks/plans/status).
- **Full suite: 150 passed**, zero regressions. Deployed to production.

## v26.0 (2026-07-26) — All-Channel Self-Evolution

Close the self-evolution loop for tacit channels (human/social/meeting/collab) — all 5 UNS channels now participate in the full cycle.

- **`kg_facts.reject()`**: new method to reject KG proposals (with reason), auto-triggers virtual consequence (match=False) → confidence adjustment → possible correction draft.
- **`consequence.virtual_consequence()`**: record a consequence without UNS event (used for human approval/rejection of tacit facts).
- **`tacit_capture` register expectation**: after proposing a KG draft, register pending consequence with tracker → when human approves/rejects, virtual consequence fires automatically.
- **`POST /evolution/kg-facts/{kid}/reject`**: API endpoint for rejecting KG proposals.
- **5 file changes, 6-step e2e verification all pass**.
- **Full suite: 150 passed**, zero regressions.

## v25.0 (2026-07-26) — Ontology Self-Growth

Automatically discover new entity/relationship types from KG proposals and propose ontology extensions through an approval gate.

- **`src/runtime/evolution/ontology.py`**: `OntologyStore` — seed ontology (16 entity types + 10 relationship types), `discover()` scans proposals for new patterns, `propose_extension()` → `proposed`, `approve_extension()` → `active`.
- **4 new API endpoints**: `GET /evolution/ontology/schema|discover`, `POST .../extensions|/extensions/{id}/approve`.
- **Knowledge graph now self-extends**: new entity types auto-discovered from tacit capture patterns.
- **Full suite: 150 passed**, zero regressions.

## v24.0 (2026-07-26) — Cross-Enterprise Federated Learning

Anonymized cross-tenant knowledge pattern aggregation and strategy signal sharing.

- **`src/runtime/federation/`** package: `federated_kg.py` (pattern aggregation, de-identified), `federated_strategy.py` (strategy signal anonymization), `api.py` (4 endpoints).
- **FederatedKG**: aggregates (predicate, object_type) patterns across tenants, computes federal trust score (validated ratio × 0.7 + cross-tenant coeff × 0.3).
- **FederationPanel.tsx**: UI for patterns/high-trust/strategy signals with privacy disclosure.
- **Full suite: 150 passed**, zero regressions. GitHub `9fefc85`.

## v23.0 (2026-07-26) — Self-Evolution Maturity

Broad-sample reflection across 4 dimensions + thin/thick Holon governance panel.

- **`reflection.reflect_broad()`**: fusion of failure cases + success cases + consequence records + KG validated facts.
- **`POST /evolution/reflect-broad`**: API endpoint that gathers 4-dimensional samples → LLM/heuristic reflection → proposed prompt version.
- **`GET /governance/panel`**: 20-agent autonomy level (thin/medium/thick), auth boundary, experience stats, consequence stats.
- **HolonGovernance.tsx**: governance panel with agent list, expandable detail cards (boundary/experience/consequence), strategy suggestions.
- **Full suite: 150 passed**, zero regressions. GitHub `01ca5ce`.

## v22.5 (2026-07-26) — Twin Dashboard

Visualization of the three-doctrine living cycle: connectionism → symbolism → behaviorism loop.

- **`GET /twin/dashboard`**: aggregated endpoint (UNS events, KG proposals, consequence stats, experience, gateway health).
- **TwinDashboard.tsx**: living cycle cards, UNS channel distribution bar chart, UNS live event feed (color-coded by channel), KG fact pipeline, blue arc stats, gateway status.
- **App.tsx**: "孪生大屏" navigation tab, 5s auto-refresh.
- **Full suite: 150 passed**, zero regressions. Vite build passed (52 modules).

## v22.0 (2026-07-26) — Blue Arc Closed Loop

Execution consequences explicitly flow back to the cognitive layer — the last arc of the three-doctrine living cycle.

- **`src/runtime/consequence.py`**: `ConsequenceTracker` — `expect_outcome()` / `record()` / `virtual_consequence()` / `_check_match()` (5% tolerance, directional validation — `_expect_decrease`/`_expect_increase`).
- **`kg_facts.validate_fact()`**: consequence match → confidence +0.10 → `validated`; mismatch → -0.15 → `needs_review`; below 0.30 → auto-propose correction draft (negated predicate ~original) → human approval gate.
- **`experience.capture_outcome()`**: consequence feedback as reinforcement signal.
- **UNS auto-capture**: gateway/system events with `action_id` auto-trigger consequence recording.
- **White paper `docs/WHITEPAPER.md`**: 11-chapter strategic whitepaper (CCI table, maturity model, federation, ontology).
- **14 unit tests, 7-step e2e verification all pass**.
- **Full suite: 150 passed** (136 → 150), zero regressions. GitHub `d6117bf`.

## v21.5 (2026-07-26) — Tacit Capture

UNS four-channel tacit signal extraction → anchored to KG as draft + experience store capture.

- **`src/runtime/tacit_capture.py`**: deterministic heuristic `extract_tacit_fact()`, UNS four-channel subscriber (human/social/meeting/collab), idempotent registration, resilient degradation.
- **`experience.capture_tacit()`**: record tacit signal as working memory.
- **`GET /experience/tacit`**: query endpoint (tacit captures + pending KG facts).
- **Extract-then-anchor pipeline**: tacit signal → `kg_facts.propose(draft)` → human approval gate.
- **5 unit tests, e2e verification all pass**.
- **Full suite: 136 passed** (131 → 136), zero regressions. GitHub `48de863`.

## v21.0 (2026-07-26) — Real-time Twin Engine (Stage 1 Phase 2)

Agent consumes real-time twin context and UNS 5-channel unification.

- **EnergyTwinDataSource**: energy-consumption twin with resilient degradation.
- **energy_carbon agent**: `analyze()` consumes `twin_context()` produces `real_time_*` conclusions.
- **UNS 5-channel normalization**: gateway/system/human/social/meeting/collab unified schema.
- **Full suite: 131 passed**, zero regressions.

把平台从「演示级数据」推向「生产级数据底座」——打通此前网关/seed 的断链。

- **DataSource 抽象与注册表** `src/runtime/data_sources/`：`DataSource` 契约 + `registry` 单例，是所有数据入口（seed/网关/MES/ERP/PLM/WMS/时序库）的统一总线；agent tools 只依赖 `registry.get(kind)`，自动 seed→live 切换。
- **MES/ERP/PLM/WMS 连接器** `connectors/domain.py`：配置驱动（base_url + api_key，环境变量注入），语义化取数（如 `mes.get_work_orders`、`wms.get_inventory`）；未配置→`is_available=False`（agent 回退 seed），调用失败→空值，**绝不抛异常阻断管道**。
- **时序数据库** `timeseries/tsdb.py`：内存环形缓冲为**始终可用的查询层**（OEE/良率/设备健康历史趋势可查）；真实后端（influxdb 等）为 best-effort 持久化适配层，不可达自动降级内存。
- **断链修复** `src/agents/supply_chain/tools.py`：供应链工具优先读 WMS/ MES/ERP live 数据，回退 seed——此前网关流/外部系统「建好但不被消费」的断链已闭合。
- **实时图谱闭环（P2）** `knowledge_graph.sync_from_sources()` + `graph_sync_loop()`：从 registry 拉 live 数据 upsert 进图谱（Neo4j/内存图，try/except 不破管），后台每 300s 周期同步，图谱随真实数据演进。事实锚点铁律：仅写实体/关系。
- **多租户数据源配置（P2）** `TenantDataSource` ORM + `persistence` + `api/data_sources.py`：`GET/POST/DELETE /data-sources` 注入/列出/删除某租户数据源并落库（重启回灌 registry）；注册表按租户隔离、未知租户回退 default。
- **lifespan 接线** `main.py`：装载默认+各租户数据源、回灌库配置、启动图谱同步循环。
- **+9 单测** `tests/test_data_sources.py` + e2e `scripts/verify_data_sources.py`（7 步）。
- **全量 119 passed（110+9），零回归**。

## v20.4 (2026-07-25) — Self-Evolution (P2)

- **Prompt self-reflection + versioning**: `src/runtime/evolution/reflection.py` `LLMReflectionService` replays an agent's recent human-rejected cases (collected by `failure_store`) through the LLM to propose a revised `system prompt`; when the LLM is unavailable it falls back to a heuristic appendix. Every candidate is versioned (`prompt_versions` table, per-agent counter) and **never auto-applied** — it lands in `proposed` and requires human `approve` → `apply`.
- **Hot-swap + one-click rollback**: `apply` hot-swaps the live agent singleton's `system_prompt` and records the prior content; `rollback` restores it. Fully audit-trailed, tenant-isolated, survives restart via SQLite + `hydrate()`.
- **RAG knowledge self-update**: `src/runtime/evolution/kg_facts.py` `KgFactStore` lets verified facts be proposed (`draft`) and, on human approval, upserted into the Neo4j knowledge graph (Entity nodes + edges + Insight), improving future RAG recall. Facts-only, never rewrites business numbers (fact-anchor rule).
- **Online preference learning (lite)**: `preference_learning.preference_calibration(agent)` derives a rolling approval-rate signal (trusted / needs_review / balanced) + most-rejected action type — a signal that drives other modules, never directly edits business numbers.
- **New API**: `POST /evolution/reflect`, `GET /evolution/failure-cases/{agent}`, `GET /evolution/prompt-versions/{agent}`, `POST /evolution/prompt-versions/{id}/approve|apply`, `POST /evolution/prompt-versions/{agent}/rollback`, `POST /evolution/kg-facts/propose`, `GET /evolution/kg-facts`, `POST /evolution/kg-facts/{id}/approve`, `GET /evolution/preference/{agent}`.
- **+11 unit tests** `tests/test_p2_evolution.py` (100% pass) + e2e `scripts/verify_p2_evolution.py`.
- **Full suite: 110 passed** (99 prior + 11 new), zero regressions.

## v20.3 (2026-07-25) — Rule-Based Self-Learning Loop (P1)

- **Experience store (preference/forbidden memory)**: `src/runtime/experience.py` `ExperienceStore` — every human approve/reject in the Intervention Center is auto-recorded as a `FeedbackRecord` (agent + action_type + decision + context), persisted to SQLite + reloaded on startup (tenant-isolated).
- **Guarded auto-tuning**: `strategy_tuner.auto_tune()` upgrades from "suggestion" to "auto-apply" with three guardrails — global switch (env `ZHIYAN_AUTO_TUNE`), per-run cap (`MAX_AUTO_PER_RUN=3`), and 24h cooldown per agent. `rollback_last_auto()` restores the pre-auto snapshot in one click (audit-trailed).
- **Feedback back-feeds tuning**: rule 2 (tighten) now also fires on recent human rejections from the experience store, even when the intervention queue shows none.
- **Wiring**: `decide_intervention` records feedback; new APIs `POST /strategy/auto-tune/run|rollback|set`, `GET /strategy/auto-tune/status`, `GET /experience/{agent}`.
- **Fixed P0 regression**: `metrics.hydrate()` now restores the original record dict from `payload` (previously wrapped in metadata, which broke `effect_report()` after a restart-with-persistence).
- **+6 unit tests** `tests/test_p1_self_learning.py` (100% pass) + e2e `scripts/verify_p1_self_learning.py`.
- **Full suite: 99 passed** (93 prior + 6 new), zero regressions.

## v20.2 (2026-07-25) — Memory Loop Closed (P0)

- **Experience memory write-back**: `apply_orchestration_result()` now implemented and wired into `engine.execute_multi()` — multi-agent orchestration insights (cross_findings + priority_actions) were previously **silently lost** (function never called). Now persisted as `Insight` nodes in the knowledge graph.
- **Generic execution memory**: `apply_execution_result()` extended beyond supply_chain/quality_trace to **all 20 Agents** — every agent's `summary` / `insights` now writes back as an `Insight` node (memory loop), plus structured deltas for oee/yield/energy/pm.
- **Recall hook**: `BaseAgent.recall(goal)` added (zero-intrusion default, safe degradation) + `src/runtime/memory.py` `MemoryStore` with CJK n-gram relevance ranking + new `GET /kg/recall` API. Orchestrator now recalls relevant history before each sub-task — agents reason **with memory**.
- **Persistent effects & audit**: `metrics` and `audit` now persist to SQLite (resilience fallback) and **reload on startup** — effect signals and audit trail survive restart, so effect-driven tuning builds on real history.
- **+13 unit tests** in `tests/test_memory_p0.py` (100% pass) + end-to-end verify `scripts/verify_memory_p0.py` (orchestration → Insight nodes → recall).
- **+1 doc** `docs/MEMORY_AND_LEARNING.md` (memory architecture, P0 closure, P1/P2 roadmap for self-learning/self-evolution).
- **Full suite: 93 passed** (80 prior + 13 new), zero regressions.

## v20.1 (2026-07-25) — Multi-Agent Orchestration

- **Multi-Agent Orchestration layer**: a single complex goal automatically fans out to 4-5 Agents that work in parallel and aggregate cross-domain insights
  - **8 preset collaboration templates** (NPI / OEE / Quality / Energy / ECO / Kitting / Cockpit / Equipment RCA)
  - **Three-tier goal decomposition**: preset templates → LLM-enhanced → keyword aggregation fallback
  - **DAG-based parallel execution** with auto-resilience (single Agent failure does not block others)
  - **6 cross-Agent insight patterns** (e.g. "supply shortage + scheduling delay", "energy + OEE idle-time savings")
  - **4 new API endpoints**: `POST /sessions/multi-agent`, `POST /sessions/{sid}/approve-multi`, `GET /sessions/multi-agent/templates`, `GET /sessions/multi-agent/decompose-preview`
- **+29 unit tests** in `tests/test_orchestrator.py` (100% pass) + end-to-end verify script `scripts/verify_orchestrator.py`
- **+1 doc** `docs/MULTI_AGENT_ORCHESTRATION.md` (full design)
- **README** updated with orchestration section
- **Zero breaking changes**: existing single-Agent flow continues to work; multi-Agent is a parallel entry point

## v20 (2026-07-24) — Full-chain Enterprise Decision

- **+9 enterprise Agents**: `aps_scheduler`, `energy_carbon`, `cost_analysis`, `demand_order`, `wms_logistics`, `compliance_q`, `executive_cockpit`, `rd_npi`, `procurement_manage`
- Platform grew **11 → 20 Agents**; MCP tools **38 → 65**
- International open-source launch: English README + CONTRIBUTING + GitHub Actions CI
- Fixed `energy_carbon` production HTTP 500 (`lines` key schema collision)
- Fixed routing ambiguity (`demand_order` / `wms_logistics` / `procurement_manage` ordering & keywords)

## v18 (P3) — Quality Compliance + Executive Cockpit

- Added `compliance_q`, `executive_cockpit` (16 → 18 Agents)
- Fixed JSX duplicate className (TS17001)

## v16 (P2) — Demand & Logistics

- Added `demand_order`, `wms_logistics` (14 → 16 Agents)
- Fixed routing conflict (demand before aps; wms before supply_chain)

## v14 (P1) — Scheduling / Energy / Cost

- Added `aps_scheduler`, `energy_carbon`, `cost_analysis` (11 → 14 Agents)

## v11 (Base) — Vertical Manufacturing Foundation

- 11 vertical manufacturing Agents + 4 protocol gateways + knowledge graph + authorization engine

---

See [docs/SUMMARY_20260724.md](docs/SUMMARY_20260724.md) for the full evolution trace.
