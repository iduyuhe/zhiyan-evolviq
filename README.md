# EvolvIQ (智衍) · AI-Native Industrial Agent Platform

> **The world's first open-source, AI-native industrial agent platform** — 20 pre-built agents spanning L2 (shop-floor protocols) to L4 (enterprise decision intelligence), designed for electronics manufacturing and semiconductors.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)
[![CI](https://github.com/iduyuhe/zhiyan-evolviq/actions/workflows/ci.yml/badge.svg)](https://github.com/iduyuhe/zhiyan-evolviq/actions/workflows/ci.yml)
[![Agents](https://img.shields.io/badge/Agents-20-blue)](https://github.com/iduyuhe/zhiyan-evolviq)
[![Version](https://img.shields.io/badge/version-v20.4-blue)](https://github.com/iduyuhe/zhiyan-evolviq)
[![Latest Release](https://img.shields.io/badge/release-v20.4%20P2%20Self--Evolution-green)](RELEASE_NOTES.md)

> 🏷 **Latest release: [v20.4 — Self-Evolution (P2)](RELEASE_NOTES.md)** (2026-07-25) · 20 Agents · Memory (P0) + Self-Learning (P1) + Self-Evolution (P2) closed loop
>
> 📖 **User Guide**: [docs/GUIDE.md](docs/GUIDE.md) · [中文指南](docs/GUIDE.zh.md)

---

## ✨ Features

- **20 Industrial Agents**: Pre-built autonomous agents for supply chain, R&D, manufacturing, quality, and enterprise decision-making
- **65 MCP Tools**: Standardized tool federation via the Model Context Protocol (HTTP + stdio dual transport)
- **4 Industrial Protocol Gateways**: Modbus, MQTT, OPC-UA, IPC-CFX — real or simulated mode
- **Multi-Agent Orchestration**: 8 preset collaboration templates (NPI / OEE / Quality / Energy / ECO ...) — automatic goal decomposition, parallel agent execution, and cross-agent insight aggregation
- **Cross-Agent Knowledge Graph**: Neo4j-backed semantic network with automatic in-memory fallback
- **Experience Memory & Recall (P0)**: Every agent execution + multi-agent orchestration writes back cross-agent insights (`Insight` nodes); agents recall relevant history before reasoning via `BaseAgent.recall(goal)` / `/kg/recall` — the memory loop is closed
- **Persistent Effects & Audit**: Metrics (autonomy rate, time saved) and audit logs survive restart via SQLite fallback — effect-driven tuning builds on real history, not a blank slate
- **Authorization Engine**: Per-agent confidence thresholds, daily autonomy limits, and approval boundaries — real-time AI behavior guardrails
- **Graceful Degradation**: Every external dependency (PostgreSQL, Neo4j, OPC-UA Server, AMQP Broker) automatically degrades to local alternatives — never blocks startup or execution
- **Multi-Tenant**: Row-level `tenant_id` isolation with API-Key authentication (`X-Tenant-Key` header)
- **Effect-Driven Strategy Tuning**: Live knob adjustment (confidence thresholds, daily limits) with audit trail
- **Self-Learning Loop (P1)**: Human approve/reject in the Intervention Center auto-feeds an agent's preference/forbidden memory; the strategy tuner auto-adjusts guardrails (with one-click rollback) — the system learns from experience, it does not just execute
- **Self-Evolution Loop (P2)**: LLM replays human-rejected cases to propose a revised agent system prompt — versioned, human-approved (never auto-applied), with hot-swap + one-click rollback; plus RAG knowledge self-update (verified facts upserted into the knowledge graph) and online preference learning (rolling approval-rate signal)
- **Apache-2.0 Licensed**: Fully open-source, no vendor lock-in

---

## 🧩 Agent Lineup (20 Agents)

### Shop-Floor Operations (11 Agents)

| Agent | Domain | Core Capability |
|-------|--------|----------------|
| `supply_chain` | Supply Chain | BOM kitting, shortage alerts, alternative sourcing |
| `pm_maintenance` | Equipment | Predictive maintenance, health scoring, spare-part lifecycle |
| `yield_analysis` | Yield | Wafer yield trend analysis, defect classification, root-cause |
| `quality_trace` | Quality | End-to-end traceability: complaint→batch→process→equipment |
| `dfm_check` | DFM | PCB/PCBA design rule checking (solder pads, trace width, solder mask) |
| `bom_selector` | BOM | Component selection, pin-to-pin alternatives, EOL alerts |
| `oee_optimizer` | OEE | Overall equipment effectiveness, six big losses analysis |
| `eco_change` | ECO | Engineering change impact analysis (BOM/WIP/inventory) |
| `smt_changeover` | SMT | Changeover optimization, SMED, feeder pre-configuration |
| `aoi_judge` | AOI | Automated optical inspection false-call filtering, threshold optimization |
| `ipc_standard` | IPC Standards | IPC-A-610 defect judgment, Class 1/2/3 grading |

### Enterprise Decision Brain (9 Agents)

| Agent | Domain | Core Capability |
|-------|--------|----------------|
| `aps_scheduler` | Scheduling | Production scheduling, capacity planning, CTP commitment |
| `energy_carbon` | Energy & ESG | Energy monitoring, carbon footprint, green ratio, ESG compliance |
| `cost_analysis` | Cost | Unit cost breakdown (BOM/labor/equipment/energy/scrap), cost reduction |
| `demand_order` | Demand & Orders | S&OP demand vs booked, backlog risk, supply rebalancing |
| `wms_logistics` | Warehouse & Logistics | Inventory health, turnover, safety-stock auto-replenishment |
| `compliance_q` | Quality Compliance | ISO certification tracking, audit findings, RoHS/REACH, auto CAPA |
| `executive_cockpit` | Executive Dashboard | KPI dashboard, budget execution, production output vs plan |
| `rd_npi` | R&D NPI | NPI project lifecycle, milestone tracking, risk identification |
| `procurement_manage` | Procurement | Supplier scorecard (delivery/quality/cost/compliance), contract management |

---

## 🎼 Multi-Agent Orchestration (V1.5)

> **The leap from "20 isolated tools" to "one collaborative team"**: a single goal like *"improve OEE"* automatically triggers 5 agents (OEE + changeover + maintenance + yield + energy) to work in parallel, then aggregates cross-domain insights into one report.

**8 preset collaboration templates** out of the box — just describe your goal, the platform picks the right team:

| Template | Trigger Words | Agents Involved |
|----------|---------------|-----------------|
| **NPI Full Evaluation** | npi, 新品导入, 量产放行, 试产 | dfm_check + bom_selector + rd_npi + smt_changeover + cost_analysis |
| **Kitting & Delivery** | 齐套, 缺料, 交期, 未交付 | supply_chain + demand_order + aps_scheduler + wms_logistics + procurement_manage |
| **OEE Improvement** | oee, 产线效率, 六大损失 | oee_optimizer + smt_changeover + pm_maintenance + yield_analysis + energy_carbon |
| **Energy & Carbon** | 能耗, 碳排放, 双碳, 绿电 | energy_carbon + oee_optimizer + cost_analysis + compliance_q |
| **Quality / Complaint RCA** | 客诉, 投诉, 退货, 不良批次 | quality_trace + yield_analysis + compliance_q + ipc_standard + executive_cockpit |
| **Executive Cockpit** | 经营, 驾驶舱, kpi, 月报, 利润 | executive_cockpit + cost_analysis + demand_order + aps_scheduler + compliance_q |
| **ECO Impact Analysis** | eco, ecn, 工程变更, 物料切换 | eco_change + bom_selector + dfm_check + aps_scheduler + compliance_q |
| **Equipment Failure RCA** | 故障, 停机, 维修, 设备异常 | pm_maintenance + yield_analysis + quality_trace + aoi_judge |

**Three-tier decomposition** (resilient fallback):
1. **Preset templates** — 8 most common scenarios, zero LLM cost
2. **LLM-enhanced** — for complex long-form goals, LLM picks the team
3. **Keyword aggregation** — always-available rule-based fallback

```bash
# Quick try (Local Python)
curl -X POST http://localhost:8000/sessions/multi-agent \
  -H "Content-Type: application/json" \
  -d '{"goal": "新产品导入评估"}'
# Returns: { session_id, plan: { sub_tasks: [...], rationale: "..." } }

curl -X POST http://localhost:8000/sessions/{session_id}/approve-multi \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
# Returns: { report: { summary, cross_findings, key_metrics, priority_actions, ... } }
```

See [`docs/MULTI_AGENT_ORCHESTRATION.md`](docs/MULTI_AGENT_ORCHESTRATION.md) for the full design.

---

## 🚀 Quick Start

### Option 1: Local Python (simplest, auto-degradation)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # Fill in your LLM_API_KEY at minimum
python -m src.runtime.main
# Open http://localhost:8000/docs
```

No PostgreSQL or Neo4j required — the platform runs with **SQLite + in-memory graph + simulated gateways**; set `ZHIYAN_DEMO_DATA=1` for demo data.

### Option 2: Docker (full stack with PG + Neo4j + frontend)

```bash
cp .env.example .env        # Fill in your LLM_API_KEY
docker compose up -d
# Frontend: http://localhost:8080     API: http://localhost:8000
```

---

## 🏗 Architecture

![EvolvIQ Architecture](architecture.svg)

### Live Console

![Console - effect-driven tuning](screenshots/console_effect.png)

**Key design principles:**
- **Deterministic by default**: All agent analysis runs on seed/production data with zero LLM hallucination
- **Facts are facts**: Every number and action is traceable, auditable, and verifiable
- **Graceful degradation**: Every dependency can fail independently — platform stays up
- **MCP-standardized**: All 65 tools exposed via Model Context Protocol (HTTP + stdio)

---

## 📚 Documentation & Community

- 🗺 Roadmap: [ROADMAP.md](ROADMAP.md)
- 🔒 Security: [SECURITY.md](SECURITY.md)
- 📝 Changelog: [CHANGELOG.md](CHANGELOG.md)
- 🏷 Release Notes: [RELEASE_NOTES.md](RELEASE_NOTES.md)
- 📖 User Guide: [docs/GUIDE.md](docs/GUIDE.md) · [中文](docs/GUIDE.zh.md)
- 📘 Application Whitepaper: [docs/WHITEPAPER.md](docs/WHITEPAPER.md)
- 📗 Technical Whitepaper: [docs/TECHNICAL_WHITEPAPER.md](docs/TECHNICAL_WHITEPAPER.md)
- ⚡ Practicality Assessment: [docs/PRACTICALITY_ASSESSMENT.md](docs/PRACTICALITY_ASSESSMENT.md)
- 🌍 Global Alignment: [docs/GLOBAL_ALIGNMENT_REPORT.md](docs/GLOBAL_ALIGNMENT_REPORT.md)
- 🏢 Enterprise Application Guide (CIO / implementation): [docs/ENTERPRISE_GUIDE.zh.md](docs/ENTERPRISE_GUIDE.zh.md)
- 🛡 Risk & Governance Whitepaper (EN): [docs/RISK_GOVERNANCE_WHITEPAPER.md](docs/RISK_GOVERNANCE_WHITEPAPER.md)
- 🛡 风险与治理白皮书 (ZH): [docs/RISK_GOVERNANCE_WHITEPAPER.zh.md](docs/RISK_GOVERNANCE_WHITEPAPER.zh.md)
- 📊 Datasheet & Competitive Comparison: [docs/DATASHEET.md](docs/DATASHEET.md)
- 🌐 Custom Domain Setup Guide: [docs/DOMAIN_GUIDE.md](docs/DOMAIN_GUIDE.md)
- 🖼 Social preview image: `og_image.png` (upload in repo **Settings → Social preview**)
- 🎬 Demo & explainer videos: see release assets / contact maintainers

## 🛡 License

Apache 2.0. See [LICENSE](LICENSE).

---

*Built for the next generation of intelligent manufacturing. EvolvIQ is a trademark of Shanghai Dute Technology Co., Ltd.*
