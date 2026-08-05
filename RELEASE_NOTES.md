# EvolvIQ (智衍) · Release Notes

> Latest stable: **v20.5 — Public Open-Source Launch** · 2026-08-05
> License: Apache-2.0 · Repo: `iduyuhe/zhiyan-evolviq`

EvolvIQ is the world's first open-source, AI-native industrial agent platform —
**25 pre-built agents** (L2 shop-floor protocols → L4 enterprise decision intelligence)
with a closed loop of **Memory (P0) → Self-Learning (P1) → Self-Evolution (P2)**.

---

## v20.5 — Public Open-Source Launch · 2026-08-05

This is the build published to GitHub as the world's first open-source, AI-native industrial agent platform.

- **25 pre-built industrial Agents** (was 20) — added the Platform & Governance layer (`industry_research`, `case_curator`, `enterprise_onboarding`, `compliance_reviewer`, `bid_intel`).
- **Production Data Layer (P1)** + **Live Knowledge Graph & Multi-Tenant Data (P2)** closed loop — agents auto-switch seed→live, every connector degrades gracefully.
- **Public online Demo** (demo tenant) + open Apache-2.0 launch.
- Continues the Memory (P0) → Self-Learning (P1) → Self-Evolution (P2) loop from v20.4.

See the [GitHub Release v20.5](https://github.com/iduyuhe/zhiyan-evolviq/releases/tag/v20.5) for the full feature list.

## v20.4 — Self-Evolution (P2) · 2026-07-25

The platform can now *improve its own instructions* from human feedback — safely, and only with human approval.

- **Prompt self-reflection + versioning** — An LLM replays an agent's recent human-rejected cases and proposes a revised `system prompt`. Every candidate is versioned and **never auto-applied**: it lands in `proposed`, then requires human `approve → apply`.
- **Hot-swap + one-click rollback** — `apply` hot-swaps the live agent's `system_prompt`; `rollback` restores the previous version. Fully audit-trailed, tenant-isolated, survives restart.
- **RAG knowledge self-update** — Verified facts proposed by humans are, on approval, upserted into the Neo4j knowledge graph, improving future recall. Facts-only; business numbers are never rewritten.
- **Online preference learning (lite)** — A rolling approval-rate signal (`trusted / needs_review / balanced`) that *informs* other modules, never edits business logic directly.
- **New API** — `/evolution/reflect`, `/evolution/failure-cases/{agent}`, `/evolution/prompt-versions/{agent}` (+ `approve`/`apply`/`rollback`), `/evolution/kg-facts` (+ `propose`/`approve`), `/evolution/preference/{agent}`.
- **+11 unit tests** (`tests/test_p2_evolution.py`) + e2e `scripts/verify_p2_evolution.py`. Full suite: **110 passed**, zero regressions.

## v20.3 — Rule-Based Self-Learning (P1) · 2026-07-25

The platform *learns from experience*, not just executes.

- **Experience store** — Every human approve/reject in the Intervention Center is recorded as a `FeedbackRecord` and persisted (tenant-isolated).
- **Guarded auto-tuning** — Strategy tuner auto-adjusts guardrails with three safety rails (global switch, per-run cap, 24h cooldown) and one-click rollback.
- **+6 unit tests** (`tests/test_p1_self_learning.py`). Full suite: **99 passed**, zero regressions.

## v20.2 — Memory Loop Closed (P0) · 2026-07-25

Agents now *remember and recall* across runs.

- **Experience memory write-back** — Multi-agent orchestration insights and every agent's results persist as `Insight` nodes in the knowledge graph (previously silently lost).
- **Recall hook** — `BaseAgent.recall(goal)` + `GET /kg/recall`: agents reason *with memory* before acting.
- **Persistent effects & audit** — Metrics and audit logs survive restart via SQLite fallback.
- **+13 unit tests** (`tests/test_memory_p0.py`). Full suite: **93 passed**, zero regressions.

---

### Earlier milestones

- **v20.1** Multi-Agent Orchestration — 8 preset collaboration templates, three-tier goal decomposition, DAG parallel execution.
- **v20** Full-chain enterprise decision — 20 Agents (11 → 20), 65 MCP tools, international open-source launch.
- **v14 / v16 / v18** Enterprise Agent waves (scheduling/energy/cost → demand/logistics → quality-compliance/executive-cockpit).
- **v11** Base — 11 vertical manufacturing Agents + 4 protocol gateways + knowledge graph + authorization engine.

See [CHANGELOG.md](CHANGELOG.md) for the full history.

---

### Upgrade / Install

```bash
pip install -e ".[dev]"          # or: docker compose up -d
cp .env.example .env             # set LLM_API_KEY at minimum
python -m src.runtime.main        # http://localhost:8000/docs
```

No PostgreSQL or Neo4j required — runs with SQLite + in-memory graph + simulated gateways.
