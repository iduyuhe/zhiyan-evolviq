# Changelog

## v20.5 (2026-07-25) — Production Data Layer (P1) + Multi-Tenant & Live Graph (P2)

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
