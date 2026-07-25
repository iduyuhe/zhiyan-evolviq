# EvolvIQ · Application Risk & Governance Whitepaper

> A formal document for **enterprise risk, compliance, audit, and IT governance committees** — it systematically maps the risks of deploying the platform and provides an actionable governance framework, authorization model, audit and incident-response mechanisms. Every governance mechanism described here corresponds to a real implementation in platform v20, not a statement of principles.

---

## 1. Purpose & Scope

### 1.1 Why a governance whitepaper

EvolvIQ packages industrial know-how into 20 agents that can **autonomously execute**. Autonomy = capability, but also = risk. When an agent can automatically lock materials, generate a CAPA, or rebalance supply, the enterprise must answer:

- Under what conditions will it make a mistake, and who is accountable?
- Who can delegate authority, how much, and how is it withdrawn?
- Are all actions auditable and traceable?
- Does data stay on-premise and never leak?
- If an external dependency fails, will the system misbehave?

This document answers those questions.

### 1.2 Relationship to other documents

| Document | Relationship |
|----------|--------------|
| Enterprise Application Guide | This paper is the **deep expansion** of Chapter 8 "Risk Control" of that guide |
| Technical Whitepaper | This paper cites its architecture but re-tells it from a governance view |
| SECURITY.md | Focuses on vulnerability disclosure; this paper focuses on **application-layer risk & the governance system** |

### 1.3 Coverage

Covers six risk classes — authorization execution, data privacy, model/algorithm, business operations, compliance/legal, organization/people; covers all deployment forms from demo to production.

---

## 2. Risk Taxonomy (Six Dimensions)

| Dimension | Concern |
|-----------|---------|
| **A. Technical Architecture** | Dependency failure, degradation behavior, fault-domain spread |
| **B. Data Privacy** | Multi-tenant isolation, egress, leakage, retention |
| **C. Model & Algorithm** | Hallucination, confidence distortion, drift, unexplainability |
| **D. Business Operations** | Mis-execution, privilege escalation, process conflict, value shortfall |
| **E. Compliance & Legal** | MLPS (China), Data Security Law, industry regs, cross-border |
| **F. Organization & People** | Unclear roles, skill gap, abuse, over-dependence |

---

## 3. Risk Register

> Each risk notes the "platform mitigation" (already implemented) + "residual risk" + "enterprise governance action".

| ID | Dim | Risk | Trigger | Impact | Platform Mitigation | Residual | Enterprise Action |
|----|-----|------|---------|--------|---------------------|----------|-------------------|
| R1 | C | Wrong advice from hallucination | LLM fabricates process conclusion | Bad decision | Confidence threshold + forced approval | Low | Start in Observe tier |
| R2 | D | Agent over-privileged auto-exec | `auto_execute` wrongly set to include money actions | Financial loss | `require_approval_actions` hard-block (code 371) | Minimal | Never whitelist approval-class actions |
| R3 | D | High-frequency daily mis-op | `max_daily` set too high | Batch errors | Daily autonomy cap (code 402) | Low | Set conservative cap |
| R4 | B | Cross-tenant data access | Multi-plant shared instance | Leak | `X-Tenant-Key` row-level isolation (persistence 127/142) | Minimal | Independent key per plant |
| R5 | A | Downtime from dependency failure | PG/Neo4j/gateway down | Business interruption | Resilient degradation (PG→SQLite etc.) | Low | Monitor gateway tab |
| R6 | B | Data leak via egress | LLM call carries sensitive fields | Compliance risk | Only LLM endpoint egresses; can be private | Medium | Private model / masking |
| R7 | C | Wrong agent routed by ambiguity | goal keyword ambiguity | Wrong analysis | `ROUTING_RULES` order rule | Low | Standardize goal wording |
| R8 | E | Industry-reg violation | Missing RoHS/IATF tracking | Fine/recall | compliance_q + auto CAPA | Low | Periodically refresh reg library |
| R9 | F | Key-person dependence on agent | Nobody reviews results | Loss of control | Mandatory human-in-the-loop | Medium | Training + governance team |
| R10 | D | Value shortfall | Demo only, no real data | Negative ROI | 3-phase rollout method | Medium | Enforce quantitative baseline |

---

## 4. Governance Architecture (Three Tiers + RACI)

```
┌─────────────────────────────────────────────────┐
│ Strategy: AI Governance Committee (CIO/Compliance/Biz) │ Set policy, approve boundaries, review incidents
├─────────────────────────────────────────────────┤
│ Tactics:  AI Governance Team (Biz+IT+Compliance ×1)    │ Monthly review, tune thresholds, manage approvals
├─────────────────────────────────────────────────┤
│ Execute:  Biz lead / IT / Gov-admin / Exec / Expert    │ Use, connect, configure, decide, verify
└─────────────────────────────────────────────────┘
```

| Activity | Committee | Gov Team | Biz Lead | IT | Gov-Admin |
|----------|:---------:|:--------:|:--------:|:--:|:---------:|
| Boundary policy | A | R | C | C | R |
| Monthly effect review | I | A | R | C | R |
| Strategic action approval | A | R | C | - | - |
| Data source onboarding | I | A | C | R | - |
| Threshold tuning | I | A | C | C | R |

A=Approve R=Responsible C=Consult I=Inform

---

## 5. Authorization Governance (Core)

### 5.1 Authorization Boundary Model (AuthBoundary, 9 fields)

Each agent holds an independent boundary, validated action-by-action by `AuthorizationEngine.evaluate()` (code `authorization.py:368`):

```
evaluate(boundary, action):
  1. if action.type ∈ require_approval_actions → force human (code 371)
  2. if action.type ∉ auto_execute_actions    → force human (code 379)
  3. if allowed_categories non-empty and category not in it → human (387)
  4. if |price change| > price_tolerance_pct   → human (390)
  5. if quantity > max_lock_qty                → human (395)
  6. if confidence < confidence_threshold      → human (398)
  7. if daily autonomous count ≥ max_daily_autonomous → human (402)
  8. all pass → auto-execute (414)
```

**Seven gates — any single failure escalates to human review.** This is the platform's hard safety floor.

### 5.2 Delegation evolution path (three tiers)

| Tier | Period | confidence | Autonomous actions | Approval actions |
|------|--------|-----------|--------------------|------------------|
| Observe | First month | 0.90 | report/task only | all |
| Collaborate | Stable | 0.75 | task + low-risk exec | money/physical |
| Autonomy | Trusted | 0.65 | most | strategic only |

Thresholds take effect **in real time via the "Strategy Tuner" console, no restart needed**.

### 5.3 Human-in-the-Loop (HITL) forced points

- **Strategic actions never enter `auto_execute_actions`**: expedite orders, contract renegotiation, budget adjustment, project re-scheduling (see each agent's default boundary)
- **Money-sensitive**: `price_tolerance_pct` constrains single-action price swing
- **Physical-sensitive**: `max_lock_qty` constrains auto-lock quantity (set 0 = never auto-lock physical goods)

### 5.4 Multi-tenant authorization isolation

`MultiTenantAuthorization` (code 425) holds an independent boundary set and daily cap per tenant; `api_key_hash → tenant_id` (`tenant_store.py:25`) ensures no cross-plant data access.

---

## 6. Data & Security Governance

| Control | Mechanism | Implementation |
|---------|-----------|----------------|
| Multi-tenant isolation | `X-Tenant-Key` header + row-level filter | persistence 127/142 |
| Audit isolation | Logs filtered by tenant | audit.py:27 |
| Minimal egress | Only LLM endpoint egresses | `.env` LLM_API_BASE |
| Privatization | Supports vLLM/Ollama, no egress | llm_client OpenAI-compatible |
| Resilient degradation | Auto-fallback on unreachable deps | manager.py / db.py |
| Secret management | `.env` not in repo, gitignored | SECURITY.md |

> **Key conclusion**: The platform can be deployed fully on-premise — data never leaves the factory. The only egress point is the LLM call, which can be fully closed by using a private model.

---

## 7. Model & Algorithm Governance

| Risk | Governance mechanism |
|------|----------------------|
| Hallucination | Confidence threshold + human approval (R1) |
| Confidence distortion | Monthly review of approval rate; tighten if low |
| Model drift | Seed data + real-source switch point, re-trainable |
| Unexplainability | Result carries reasoning-chain tab + knowledge-graph trace |
| Single-point dependency | Hot-swap any OpenAI-compatible model |

---

## 8. Audit & Traceability

### 8.1 Audit log

- **Endpoint**: `GET /audit/logs` (audit.py:15)
- **Contents**: session_id / event_type / actor / detail / tenant_id / timestamp
- **Storage**: Database preferred, falls back to memory when unavailable (audit.py:23-27)
- **Isolation**: All queries filtered by current tenant (audit.py:19)

`log_audit(session_id, event_type, actor, detail, tenant_id)` (persistence.py:86) records every key action.

### 8.2 End-to-end traceability

`apply_execution_result(tenant_id, agent_name, session_id, result)` (knowledge_graph.py:269) automatically writes each execution result into the cross-agent knowledge graph, tagged with `tenant`, forming a traceable chain "quality case → equipment → part → line".

### 8.3 Compliance evidence export

Audit log + knowledge-graph edges = a retroactively traceable compliance evidence chain, supporting regulatory inspection and internal audit.

---

## 9. Resilience & Business Continuity (BCP)

| Dependency | On unreachable | After recovery | Fault domain |
|-----------|---------------|----------------|--------------|
| PostgreSQL | Fallback to SQLite file | Switch back next startup | Data layer |
| Neo4j | Fallback to in-memory adjacency | Rebuild and switch back | Graph layer |
| OPC-UA Server | simulated mode | Auto switch to live | Ingestion layer |
| AMQP Broker | simulated mode | Auto switch to live | Ingestion layer |

**Design rule**: Except for the LLM Key, no external dependency must be online; any failure means the system **never goes down and never mis-executes** (degradation only affects data freshness, never triggers over-privileged actions).

---

## 10. Compliance Mapping

| Reg / Standard | Corresponding governance mechanism |
|---------------|-----------------------------------|
| MLPS 2.0 (China) | Multi-tenant isolation, audit log, minimal egress |
| Data Security Law / PIPL | Private deployment, no egress, controllable retention |
| GDPR (if EU involved) | Data isolation, deletable (tenant-level) |
| ISO/IEC 27001 | Access control, audit, BCP |
| IATF 16949 / RoHS / REACH | compliance_q + auto CAPA tracking |

---

## 11. Governance Operations

### 11.1 Monthly review checklist

```
□ Per-agent approval rate / rejection rate (high rejection → tighten threshold)
□ Autonomy-rate trend (abnormal spike → re-review delegation)
□ Audit log sampling (attribute abnormal actions)
□ New data-source onboarding review
□ Regulation-library update confirmation
```

### 11.2 Effect-metrics dashboard

| Metric | Meaning | Governance signal |
|--------|---------|-------------------|
| Autonomy rate | Share of autonomous execution | Delegation level |
| Approval rate | Share of submissions approved | Human trust |
| Rejection rate | Share of submissions rejected | Agent judgment quality |

### 11.3 Incident response flow

```
Detect anomaly → Gov-admin pauses that agent's boundary (enabled=False) →
Gov team attributes cause → Committee grades severity → Fix (tune threshold / edit whitelist) →
Post-mortem into Risk Register → Update reg library if needed
```

---

## 12. Governance Maturity Roadmap

| Level | Name | Characteristic |
|-------|------|----------------|
| L1 | Observe | All human-approved, agent reports only |
| L2 | Collaborate | Low-risk actions autonomous, money/physical submitted |
| L3 | Autonomy | Most actions autonomous, strategic only submitted |
| L4 | Self-governing | Cross-agent orchestration + adaptive threshold (roadmap远期) |

Recommend starting at L1, assessing one level up per quarter, **never skip levels**.

---

## 13. Disclaimer

This document is written against the real implementation of EvolvIQ v20 and describes the **capabilities** the platform provides for governance. An enterprise's actual risk level depends on deployment form, authorization configuration, and operational discipline — the platform provides the tools; the governance responsibility rests with the enterprise. We recommend building the enterprise's own AI governance system on top of this whitepaper.

---

*Companion documents: Enterprise Application Guide (rollout), Technical Whitepaper (architecture), SECURITY.md (vulnerability disclosure).*
