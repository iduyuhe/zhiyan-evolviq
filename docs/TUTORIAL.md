# Tutorial: Build a New Agent

> This guide walks you through adding a brand-new Agent to EvolvIQ, using
> `supply_chain` (the reference template) as the base. By the end you will
> have registered an Agent that is routable, callable via MCP, guarded by an
> authorization boundary, and rendered in the Studio UI.

EvolvIQ currently ships **20 Agents** across R&D, Manufacturing, and Operations.
Every Agent implements the same contract, so the platform can route, execute,
federate, and authorize them uniformly.

---

## 0. The Contract (read this first)

Every Agent subclasses `BaseAgent` and implements **one async method**:

```python
# src/agents/base.py
class BaseAgent:
    name: str
    description: str

    async def analyze(self, goal: str) -> dict:
        """Take a natural-language goal and return a result dict."""
        ...
```

The returned `dict` is what the API and UI consume. Recommended keys:

| Key | Type | Meaning |
|-----|------|---------|
| `status` | str | `"completed"` / `"pending_approval"` / `"failed"` |
| `agent` | str | your agent name (echo) |
| `summary` | str | one-line human summary |
| `metrics` | dict | structured KPIs (dashboards, ROI) |
| `actions_taken` | list | autonomous / pending actions (audit trail) |
| `warning` | list | risk flags for human attention |

> ⚠️ **Do not reuse the `lines` key** unless you follow the OEE/energy schema
> rules in `engine.py`. Use your own top-level keys to avoid `KeyError` 500s.

---

## 1. Scaffold the module

```bash
mkdir -p src/agents/inventory_health
touch src/agents/inventory_health/__init__.py
touch src/agents/inventory_health/agent.py
touch src/agents/inventory_health/tools.py
```

- `agent.py` — your `Agent` class + a module-level singleton (`XxxAgent()`)
- `tools.py` — optional data/tool layer (seed data, external calls)
- `__init__.py` — can stay empty, or re-export the singleton

---

## 2. Implement the Agent

Minimal skeleton (adapted from `src/agents/supply_chain/agent.py`):

```python
# src/agents/inventory_health/agent.py
import logging
from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class InventoryHealthAgent(BaseAgent):
    name = "inventory_health"
    description = "库存健康度评估、呆滞预警、补货建议"

    def __init__(self):
        # optionally wire a tools layer: self.tools = InventoryHealthTools()
        pass

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[inventory_health] goal: {goal[:80]}")
        # 1. parse params from goal (regex / LLM)
        # 2. gather data via self.tools.* or seed data
        # 3. compute deterministic results (facts, not LLM guesses)
        health_score = 87.3
        return {
            "status": "completed",
            "agent": self.name,
            "summary": f"库存健康度 {health_score}%，发现 2 项呆滞风险",
            "metrics": {
                "health_score": health_score,
                "stagnant_skus": 2,
                "turnover_days": 41.5,
            },
            "actions_taken": [],
            "warning": ["SKU-A102 周转 > 90 天，建议促销清库"],
        }


# Module-level singleton — referenced by AGENT_REGISTRY
inventory_health_agent = InventoryHealthAgent()
```

**Golden rules**
- Keep numbers **deterministic** (seed data + rules). EvolvIQ's "fact anchor"
  principle means metric deltas must be reproducible, never LLM-hallucinated.
- Autonomous actions go into `actions_taken` with a `status` of
  `auto_executed` or `pending_approval` — the authorization engine reads these.

---

## 3. Register routing — `src/runtime/agent/router.py`

### 3a. AGENT_REGISTRY (line ~35)

Add one line mapping your name → `(module, singleton_var)`:

```python
AGENT_REGISTRY: dict[str, tuple[str, str]] = {
    # ... existing agents ...
    "inventory_health": ("src.agents.inventory_health.agent", "inventory_health_agent"),
}
```

Imports are **lazy** (resolved inside `get_agent()`), so an unused Agent is never
loaded. Do not add a top-level `import`.

### 3b. ROUTING_RULES (line ~65) — ⚠ ORDER MATTERS

`route_goal()` scans the list **top-to-bottom** and returns on the first keyword
match. Put **specific** agents **before** broad ones, or a broad agent steals
the intent.

```python
ROUTING_RULES = [
    # ... existing rules ...
    # Put inventory_health BEFORE supply_chain if "库存" could collide:
    (["库存健康", "呆滞", "周转", "stagnant", "inventory health", "slow moving"], "inventory_health"),
    (["物料", "齐套", "缺料", "BOM", "库存", "PO", ...], "supply_chain"),
    # ...
]
```

**Real past bugs fixed by ordering:**
- `demand_order` must precede `aps_scheduler` (else "交期风险" → aps).
- `wms_logistics` must precede `supply_chain` **and drop the bare word "库存"**
  (else it hijacks supply_chain's inventory queries).
- `procurement_manage` must precede `supply_chain` and use **compound** words
  only ("供应商绩效", not "供应") — else "供应" → supply_chain.

---

## 4. Expose MCP tools — `src/runtime/mcp/federation.py`

If your Agent has callable tools, register them so external systems can invoke
them over MCP (HTTP `/mcp/tools` or stdio).

### 4a. `_INSTANCES` (line ~46)

```python
from src.agents.inventory_health.tools import InventoryHealthTools

_INSTANCES = {
    # ... existing ...
    "inventory_health": InventoryHealthTools(),
}
```

### 4b. `TOOL_REGISTRY` (line ~71)

Namespace is `{agent}__{method}`. Tuple = `(agent, method, description, params)`:

```python
TOOL_REGISTRY = {
    # ... existing ...
    "inventory_health__health_score": (
        "inventory_health", "compute_health", "计算库存健康度", {"warehouse": "string"}
    ),
    "inventory_health__list_stagnant": (
        "inventory_health", "list_stagnant", "列出呆滞SKU", {"threshold_days": "integer"}
    ),
}
```

No tool layer? Skip this step — the Agent is still fully routable & callable.

---

## 5. Authorization boundary — `src/runtime/core/authorization.py`

Every Agent needs a default `AuthBoundary`, or `/strategy` will show the wrong
Agent count and `get_for_agent()` returns `None`. Add one in
`_build_default_boundaries()` (line ~35):

```python
defaults.append(AuthBoundary(
    id="ab-inventory-health-default",
    name="库存健康默认边界",
    agent="inventory_health",
    allowed_categories=["成品", "原材料", "半成品"],
    price_tolerance_pct=0.0,
    max_lock_qty=0,
    confidence_threshold=0.8,
    auto_execute_actions=["notify", "adjust_priority"],
    require_approval_actions=["auto_purchase", "write_off"],
    max_daily_autonomous=15,
    enabled=True,
))
```

Fields: `id`, `name`, `agent`, `allowed_categories`, `price_tolerance_pct`,
`max_lock_qty`, `confidence_threshold`, `auto_execute_actions`,
`require_approval_actions`, `max_daily_autonomous`, `enabled`.

The engine reads `confidence_threshold` / `max_daily_autonomous` **live** on
every action, so tuning them at runtime immediately changes behavior.

---

## 6. Frontend wiring — `studio/src` (4 places)

### 6a. `components/AgentSelector.tsx` — `SCENARIO_GROUPS`
Add your Agent to the right scenario group (R&D / Manufacturing / Operations).

### 6b. `App.tsx` — dispatch list
Add `inventory_health` to the agent dispatch array so the UI can target it.

### 6c. `components/GenericResultView.tsx`
- Add an `AGENT_META` entry (`label`, `icon`, `accent`).
- Add a `getTabs()` case returning your result tabs.
- Add a render function for your metrics/actions/warning blocks.

### 6d. `components/StrategyTuningTab.tsx`
Bump the Agent count text if it is hard-coded (e.g. "20 Agents" → "21 Agents").

> If you skip the UI, the Agent still works via API/MCP — the Studio just won't
> show a dedicated view.

---

## 7. Tests

Add a routing assertion so a regression can't silently re-route your Agent:

```python
# tests/test_routing.py
from src.runtime.agent.router import route_goal

def test_inventory_health_routing():
    assert route_goal("评估库存健康度并预警呆滞") == "inventory_health"
    # must NOT be stolen by supply_chain
    assert route_goal("检查呆滞料") != "supply_chain"
```

Run the suite:

```bash
pytest tests/ -q
```

---

## 8. End-to-end smoke test (local)

```python
import asyncio
from src.runtime.agent.router import get_agent

async def smoke():
    agent = get_agent("inventory_health")
    result = await agent.analyze("评估库存健康度，标出呆滞SKU")
    assert result["status"] == "completed"
    print(result["summary"])

asyncio.run(smoke())
```

Or hit the live API:

```bash
curl -X POST http://localhost:8000/sessions/quick-check \
  -H "Content-Type: application/json" \
  -d '{"goal":"评估库存健康度并预警呆滞"}'
```

---

## 9. Pre-PR checklist

- [ ] `BaseAgent.analyze(goal) -> dict` implemented
- [ ] `AGENT_REGISTRY` entry added (lazy module path)
- [ ] `ROUTING_RULES` entry added **in the correct order**
- [ ] `AuthBoundary` added in `_build_default_boundaries`
- [ ] (optional) `federation._INSTANCES` + `TOOL_REGISTRY` entries
- [ ] (optional) Studio 4-point wiring
- [ ] Routing test added & `pytest` green
- [ ] Numbers deterministic (seed data, not LLM guesses)
- [ ] Did **not** reuse the `lines` key unless following OEE/energy schema

---

## Reference files

| Concern | File | Anchor |
|---------|------|--------|
| Contract | `src/agents/base.py` | `class BaseAgent` |
| Routing registry | `src/runtime/agent/router.py` | `AGENT_REGISTRY` (L35) |
| Routing rules | `src/runtime/agent/router.py` | `ROUTING_RULES` (L65) |
| MCP federation | `src/runtime/mcp/federation.py` | `_INSTANCES` (L46), `TOOL_REGISTRY` (L71) |
| Authorization | `src/runtime/core/authorization.py` | `_build_default_boundaries` (L35) |
| Reference agent | `src/agents/supply_chain/agent.py` | full implementation |
| UI wiring | `studio/src/components/*.tsx` | `AgentSelector`, `GenericResultView` |

Welcome to the EvolvIQ Agent ecosystem — PRs are appreciated!
