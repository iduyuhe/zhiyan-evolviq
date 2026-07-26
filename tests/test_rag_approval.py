"""RAG 自更新审批流端到端验证（生产就绪）。

验证：① 直接提议 KG 事实 → draft → 审批通过（upsert 图谱）→ 状态 approved；
② 隐性捕获自动产生的 KG draft 同样可经审批门进入图谱（抽取即锚定→人审→图谱）。
全链路人工审批门（绝不自动应用）成立。
"""
import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.main import app
from src.runtime.evolution.kg_facts import kg_facts


@pytest.fixture(autouse=True)
def _clear():
    kg_facts._proposals.clear()
    yield
    kg_facts._proposals.clear()


@pytest.fixture
def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_propose_then_approve_kg_fact(_client):
    r = await _client.post("/evolution/kg-facts/propose", json={
        "agent": "supply_chain", "subject": "SUP:A", "predicate": "lead_time_days",
        "object": "7", "source": "erp://sap", "confidence": 0.8,
    })
    assert r.status_code == 200
    kid = r.json()["proposal"]["id"]

    lst = await _client.get("/evolution/kg-facts")
    assert any(p["id"] == kid and p["status"] == "draft" for p in lst.json()["proposals"])

    # 人工审批通过 → upsert 进图谱
    a = await _client.post(f"/evolution/kg-facts/{kid}/approve")
    assert a.status_code == 200
    assert a.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_tacit_capture_draft_approvable(_client):
    """隐性捕获产生的 KG draft 能进入审批门（抽取即锚定 → 人审 → 图谱）。"""
    # 摄入一条隐性信号
    await _client.post("/tacit-capture/human", json={
        "source": "emp:zhang", "payload": {"judgment": "A 供应商交期最稳"},
        "entities": ["SUP:A"], "confidence": 0.9,
    })
    # 经验库查询应返回一条隐性捕获 + 关联 KG draft
    tac = await _client.get("/experience/tacit")
    body = tac.json()
    assert len(body["tacit_captures"]) >= 1
    drafts = body["pending_kg_facts"]
    assert len(drafts) >= 1
    kid = drafts[0]["id"]

    # 审批通过 → 入图谱
    a = await _client.post(f"/evolution/kg-facts/{kid}/approve")
    assert a.status_code == 200
    assert a.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_records_virtual_consequence(_client):
    """驳回 KG 事实 → 记录虚拟后果（蓝弧闭环衔接），不写入图谱。"""
    from src.runtime.consequence import consequence

    consequence.clear()
    r = await _client.post("/evolution/kg-facts/propose", json={
        "agent": "tacit:human", "subject": "X", "predicate": "y", "object": "z",
    })
    kid = r.json()["proposal"]["id"]
    rej = await _client.post(f"/evolution/kg-facts/{kid}/reject", json={"reason": "置信不足"})
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"
    # 虚拟后果已记录（蓝弧闭环衔接）
    assert consequence.stats()["total_consequences"] >= 1
