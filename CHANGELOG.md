# Changelog

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
