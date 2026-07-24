# EvolvIQ · User Guide

> Quick-start guide for all 20 industrial agents — from goal setting to result interpretation.

See the Chinese version ([GUIDE.zh.md](GUIDE.zh.md)) for the most up-to-date content.

## Quick Reference

### Access
- **Production**: `http://43.153.172.52:3006`
- **Local**: `python -m src.runtime.main`
- **Docker**: `docker compose up -d`

### 20 Agents at a Glance

| Group | Agents |
|-------|--------|
| 📦 Supply Chain | `supply_chain` |
| 🔬 R&D | `dfm_check` · `bom_selector` · `eco_change` |
| ⚙️ Manufacturing | `pm_maintenance` · `oee_optimizer` · `smt_changeover` · `aoi_judge` |
| 🛡️ Quality | `yield_analysis` · `quality_trace` · `ipc_standard` |
| 🧠 Enterprise | `aps_scheduler` · `energy_carbon` · `cost_analysis` · `demand_order` · `wms_logistics` · `compliance_q` · `executive_cockpit` · `rd_npi` · `procurement_manage` |

### How to Use

1. **Select an Agent** from the top-right dropdown
2. **Type your goal** in natural language (or pick an example)
3. **Review the result** — structured tabs with metrics, details, and actions
4. **Tune behavior** in the Strategy Control panel (confidence thresholds, daily limits)

### Key Features

- **20 pre-built agents** — zero setup, zero training
- **65 MCP tools** — standardized API for external integration
- **Graceful degradation** — never crashes on external dependency failure
- **Authorization guardrails** — confidence limits, daily caps, human approval gates
- **Multi-tenant** — row-level isolation via `X-Tenant-Key` header

### Architecture

```
User → Studio (React) → Runtime API (FastAPI)
                           ├─ Router (20 agents)
                           ├─ Engine (plan → execute)
                           ├─ Federation (65 MCP tools)
                           ├─ Authorization Engine
                           ├─ 4 Protocol Gateways
                           ├─ Knowledge Graph (Neo4j/memory)
                           └─ LLM Client (DeepSeek + Hunyuan)
```
