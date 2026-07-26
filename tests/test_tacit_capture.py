"""隐性信号捕获摄入测试（v21.5 落地入口）。

验证：信号经 POST /tacit-capture/{channel} 进入 UNS → 订阅管道完成
「抽取即锚定」——经验库捕获 + 知识图谱 draft 提议。
"""
import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.main import app
from src.runtime.experience import experience
from src.runtime.uns import uns, CHANNEL_HUMAN
from src.runtime.tacit_capture import extract_tacit_fact


@pytest.fixture
def _client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_ingest_human_signal_via_api(_client):
    before = len(experience.tacit_captures(tenant="default"))
    resp = await _client.post(
        "/tacit-capture/human",
        json={"source": "emp:zhang", "payload": {"judgment": "这条产线换型风险偏高，建议先小批验证"},
              "entities": ["LINE:3", "EMP:zhang"], "confidence": 0.9},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "captured"
    assert body["channel"] == "human"
    # 经验库应新增一条隐性捕获
    caps = experience.tacit_captures(tenant="default")
    assert len(caps) > before
    latest = caps[0]
    assert latest["channel"] == "human"
    assert "换型风险" in latest["context"]


@pytest.mark.asyncio
async def test_invalid_channel_rejected(_client):
    resp = await _client.post(
        "/tacit-capture/gateway",
        json={"source": "x", "payload": {"k": "v"}},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_pipeline_anchors_to_kg(_client):
    """UNS 四路信号 → 抽取 → KG draft 提议（抽取即锚定）。"""
    from src.runtime.evolution.kg_facts import kg_facts

    n_prop_before = len(kg_facts.list_proposals())
    ev = uns.publish_human(
        source="emp:li",
        payload={"decision_rationale": "优先保供 A 供应商，因其交期最稳"},
        entities=["SUP:A", "EMP:li"],
        type="tacit_judgment",
        confidence=0.8,
    )
    fact = extract_tacit_fact(ev)
    assert fact["predicate"] in ("tacit_judges", "signals")
    assert len(kg_facts.list_proposals()) > n_prop_before


def test_extract_uses_type_predicate():
    class _Ev:
        channel = "social"
        type = "business_event"
        source = "wecom:g1"
        payload = {"summary": "Q3 订单环比下滑 12%"}
        entities = []

    f = extract_tacit_fact(_Ev())
    assert f["predicate"] == "observed_in"
    assert "订单" in f["object_val"]
