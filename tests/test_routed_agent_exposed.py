"""F4 回归测试：路由透明度——接口层回显「实际处理该目标的 Agent」。

背景（审计发现的可用性缺口）：
引擎 `plan()` 始终按目标文本路由（`route_goal(goal)`），完全忽略前端侧栏所选 Agent。
用户因此可能出现「选了 A、实际由 B 处理」而毫无感知，甚至用 A 的结果视图渲染 B 的结论。

修复约束：不改路由架构（不扩边缘），只在接口层把真实路由结果暴露出来，
由前端回显 + 差异提示，并据此选择正确的结果视图。
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Request

from src.runtime.agent.router import route_goal

FAKE_RESULT = {
    "status": "completed",
    "summary": "演示结论",
    "bom": "SMIC-28nm-Logic",
    "completeness_pct": 100,
    "check_details": [],
    "actions_taken": [],
    "warning": [],
}

ROUTED = "aps_scheduler"


@pytest.fixture
async def client(monkeypatch):
    from src.runtime.api import sessions as s_mod
    from src.runtime.api.deps import get_tenant

    app = FastAPI()
    app.include_router(s_mod.router)

    def _tenant_from_header(request: Request) -> str:
        return request.headers.get("X-Tenant-Key", "telecom")

    app.dependency_overrides[get_tenant] = _tenant_from_header

    class FakeEngine:
        """模拟引擎：plan 后把路由到的 agent 写进会话（与真实引擎行为一致）。"""

        def __init__(self) -> None:
            self._sessions: dict[str, dict] = {}

        async def plan(self, session_id, goal, *a, **k):
            self._sessions[session_id] = {"agent": ROUTED, "goal": goal}
            return "## 规划"

        async def execute(self, session_id, *a, **k):
            return dict(FAKE_RESULT)

        def get_session(self, session_id):
            return self._sessions.get(session_id)

    engine = FakeEngine()
    monkeypatch.setattr(s_mod, "get_engine", lambda: engine)

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(s_mod, "_meter_insight", _noop)
    monkeypatch.setattr(s_mod, "_track_session_start", _noop)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def test_quick_check_exposes_routed_agent(client):
    r = await client.post("/sessions/quick-check", json={"goal": "排一版本周产线排程"})
    assert r.status_code == 200
    body = r.json()
    assert body["routed_agent"] == ROUTED
    # F1 标注不得被 F4 改动破坏
    assert body["result"]["data_source"] in ("real", "demo")


async def test_create_session_exposes_routed_agent(client):
    r = await client.post("/sessions", json={"goal": "排一版本周产线排程"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "awaiting_approval"
    assert body["routed_agent"] == ROUTED


async def test_approve_exposes_routed_agent(client):
    created = await client.post("/sessions", json={"goal": "排一版本周产线排程"})
    sid = created.json()["session_id"]

    r = await client.post(f"/sessions/{sid}/approve", json={"approved": True})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["routed_agent"] == ROUTED
    assert body["result"]["data_source"] in ("real", "demo")


async def test_routed_agent_absent_engine_is_safe(monkeypatch):
    """引擎无 get_session（结构不确定）时须安全降级为 None，绝不 500。"""
    from src.runtime.api import sessions as s_mod
    from src.runtime.api.deps import get_tenant

    app = FastAPI()
    app.include_router(s_mod.router)
    app.dependency_overrides[get_tenant] = lambda: "telecom"

    class BrokenEngine:
        async def plan(self, *a, **k):
            return "## 规划"

        async def execute(self, *a, **k):
            return dict(FAKE_RESULT)

    monkeypatch.setattr(s_mod, "get_engine", lambda: BrokenEngine())

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(s_mod, "_meter_insight", _noop)
    monkeypatch.setattr(s_mod, "_track_session_start", _noop)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/sessions/quick-check", json={"goal": "任意目标"})
    assert r.status_code == 200
    assert r.json()["routed_agent"] is None


def test_router_ambiguity_is_deterministic():
    """锁定审计中记录的路由歧义样例，确保回显的是真实路由结果而非猜测。

    ROUTING_RULES 顺序敏感：demand_order（含「交期风险」）排在 aps_scheduler（含「交期」）之前。
    """
    # 「交期风险」是 demand_order 的专属复合词，先于 aps_scheduler 命中
    assert route_goal("分析交期风险") == "demand_order"
    # 单独的「交期」（不带需求/订单等前序关键词）才落到 aps_scheduler
    assert route_goal("这批货交期怎么保") == "aps_scheduler"
    # 兜底：无任何关键词命中 → supply_chain
    assert route_goal("随便说点什么") == "supply_chain"
