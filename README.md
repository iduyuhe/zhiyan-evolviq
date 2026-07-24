# EvolvIQ (智衍) · AI-Native Industrial Agent Platform

> **The world's first open-source, AI-native industrial agent platform** — 20 pre-built agents spanning L2 (shop-floor protocols) to L4 (enterprise decision intelligence), designed for electronics manufacturing and semiconductors.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)

---

## ✨ Features

- **20 Industrial Agents**: Pre-built autonomous agents for supply chain, R&D, manufacturing, quality, and enterprise decision-making
- **65 MCP Tools**: Standardized tool federation via the Model Context Protocol (HTTP + stdio dual transport)
- **4 Industrial Protocol Gateways**: Modbus, MQTT, OPC-UA, IPC-CFX — real or simulated mode
- **Cross-Agent Knowledge Graph**: Neo4j-backed semantic network with automatic in-memory fallback
- **Authorization Engine**: Per-agent confidence thresholds, daily autonomy limits, and approval boundaries — real-time AI behavior guardrails
- **Graceful Degradation**: Every external dependency (PostgreSQL, Neo4j, OPC-UA Server, AMQP Broker) automatically degrades to local alternatives — never blocks startup or execution
- **Multi-Tenant**: Row-level `tenant_id` isolation with API-Key authentication (`X-Tenant-Key` header)
- **Effect-Driven Strategy Tuning**: Live knob adjustment (confidence thresholds, daily limits) with audit trail
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

```
┌──────────────────────────────────────────────────────┐
│                   Studio (React/TS)                   │
│   Goal Input → Agent Selector → Result View → Console │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP (REST API)
┌──────────────────────▼───────────────────────────────┐
│                  Runtime (FastAPI)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐  │
│  │ Router   │ │ Engine   │ │ Authorization Engine  │  │
│  │ (20 Ag.) │ │ (plan→   │ │ (confidence/limits/   │  │
│  │          │ │ execute) │ │  approval boundaries) │  │
│  └──────────┘ └──────────┘ └──────────────────────┘  │
│  ┌──────────────────────────────────────────────┐    │
│  │         MCP Federation (65 tools)            │    │
│  │  HTTP endpoint · stdio server · dispatch     │    │
│  └──────────────────────────────────────────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐   │
│  │ 4 Proto- │ │Knowledge │ │ LLM Client          │   │
│  │ col Gate │ │ Graph    │ │ (DeepSeek + Hunyuan) │   │
│  └──────────┘ └──────────┘ └────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

**Key design principles:**
- **Deterministic by default**: All agent analysis runs on seed/production data with zero LLM hallucination
- **Facts are facts**: Every number and action is traceable, auditable, and verifiable
- **Graceful degradation**: Every dependency can fail independently — platform stays up
- **MCP-standardized**: All 65 tools exposed via Model Context Protocol (HTTP + stdio)

---

## 🛡 License

Apache 2.0. See [LICENSE](LICENSE).

---

*Built for the next generation of intelligent manufacturing. EvolvIQ is a trademark of Shanghai Dute Technology Co., Ltd.*
