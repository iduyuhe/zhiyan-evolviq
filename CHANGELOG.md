# Changelog

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
