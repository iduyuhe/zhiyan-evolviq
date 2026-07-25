"""P2 自进化层测试——失败采集 / Prompt 版本化 / 自反思兜底 / KG 事实 / 偏好校准 / API 接线。

测试铁律：
- 每个用例重置相关单例（autouse fixture），互不污染。
- Prompt 热替换通过 monkeypatch `get_agent` 指向假对象，不碰真实 Agent 单例。
- LLM / Neo4j 通过 monkeypatch 隔离，保证确定性、无外部依赖。
"""

import pytest

from src.runtime.experience import experience
from src.runtime.evolution import prompt_versions, kg_facts, failure_store, preference_learning
from src.runtime.evolution import reflection as reflection_svc


@pytest.fixture(autouse=True)
def _reset_singletons():
    # 清空各单例内存态，并断开落库 sink（测试不依赖 DB）
    experience._records = []
    experience._async_sink = None
    prompt_versions._versions = []
    prompt_versions._active = {}
    prompt_versions._applied_stack = {}
    prompt_versions._snapshot = {}
    prompt_versions._sink = None
    kg_facts._proposals = []
    kg_facts._sink = None
    yield
    # teardown：还原
    experience._records = []
    prompt_versions._versions = []
    prompt_versions._active = {}
    prompt_versions._applied_stack = {}
    prompt_versions._snapshot = {}
    kg_facts._proposals = []


# ---------- P2-1 失败案例采集 ----------
def test_failure_collection_empty_when_no_feedback():
    assert failure_store.collect_failure_cases("supply_chain") == []


def test_failure_collection_from_rejections():
    experience.record_feedback("default", "supply_chain", "lock_alternative", "rejected",
                               context="锁定了未评估的替代料", note="应先评估")
    cases = failure_store.collect_failure_cases("supply_chain")
    assert len(cases) == 1
    assert cases[0].kind == "rejection"
    assert cases[0].action_type == "lock_alternative"
    # 其他 Agent 不受影响
    assert failure_store.collect_failure_cases("quality_trace") == []


# ---------- P2-2 Prompt 版本化 + 热替换 + 回滚 ----------
def test_prompt_version_lifecycle(monkeypatch):
    import sys
    fake = type("A", (), {"system_prompt": "BASE PROMPT"})()
    pv_mod = sys.modules["src.runtime.evolution.prompt_versions"]
    monkeypatch.setattr(pv_mod, "get_agent", lambda a: fake)

    v1 = prompt_versions.propose("default", "supply_chain", "PROMPT V1", proposer="heuristic")
    assert v1["status"] == "proposed"
    # 未 approve 不应被 apply
    with pytest.raises(KeyError):
        prompt_versions.apply("nope")

    prompt_versions.approve(v1["id"])
    applied = prompt_versions.apply(v1["id"])
    assert applied["status"] == "active"
    assert fake.system_prompt == "PROMPT V1"  # 热替换生效

    # 再生成一版并应用
    v2 = prompt_versions.propose("default", "supply_chain", "PROMPT V2", parent_version=1, proposer="heuristic")
    prompt_versions.approve(v2["id"])
    prompt_versions.apply(v2["id"])
    assert fake.system_prompt == "PROMPT V2"
    assert prompt_versions.active_version("supply_chain")["id"] == v2["id"]

    # 回滚 → 恢复到 V1
    rb = prompt_versions.rollback("supply_chain")
    assert rb["status"] == "rolled_back"
    assert fake.system_prompt == "PROMPT V1"
    assert prompt_versions.active_version("supply_chain")["id"] == v1["id"]


# ---------- P2-3 LLM 自反思 ----------
@pytest.mark.asyncio
async def test_reflection_no_failures_returns_current(monkeypatch):
    res = await reflection_svc.reflect("supply_chain", [], "CURRENT")
    assert res.source == "none"
    assert res.proposed_prompt == "CURRENT"


@pytest.mark.asyncio
async def test_reflection_heuristic_fallback_when_llm_unavailable(monkeypatch):
    # 模拟 LLM 不可用
    fake_llm = type("L", (), {"available": False})()
    monkeypatch.setattr("src.common.llm_client.llm_client", fake_llm)

    cases = [failure_store.FailureCase("1", "supply_chain", "rejection", "lock_alternative",
                                       "锁定未评估替代料", "应先评估", "")]
    res = await reflection_svc.reflect("supply_chain", cases, "BASE")
    assert res.source == "heuristic"
    assert "自进化提示附录" in res.proposed_prompt
    assert res.proposed_prompt.startswith("BASE")


@pytest.mark.asyncio
async def test_reflection_uses_llm_when_available(monkeypatch):
    class FakeLLM:
        available = True

        async def chat(self, messages, **kw):
            return "<PROMPT>REVISED PROMPT</PROMPT>\n变更理由：加强替代料评估约束。"

    monkeypatch.setattr("src.common.llm_client.llm_client", FakeLLM())
    cases = [failure_store.FailureCase("1", "supply_chain", "rejection", "lock_alternative",
                                       "锁定未评估替代料", "应先评估", "")]
    res = await reflection_svc.reflect("supply_chain", cases, "BASE")
    assert res.source == "llm"
    assert res.proposed_prompt == "REVISED PROMPT"
    assert "加强替代料评估" in res.rationale


# ---------- P2-4 RAG 知识自更新 ----------
@pytest.mark.asyncio
async def test_kg_fact_propose_and_approve(monkeypatch):
    # 隔离 Neo4j：把 merge 调用打成 no-op，验证 store 逻辑
    calls = {}

    async def fake_merge_node(label, nid, props=None):
        calls.setdefault("nodes", []).append(nid)

    async def fake_merge_edge(f, t, et, props=None):
        calls.setdefault("edges", []).append((f, t, et))

    monkeypatch.setattr("src.common.neo4j_client.merge_node", fake_merge_node)
    monkeypatch.setattr("src.common.neo4j_client.merge_edge", fake_merge_edge)

    p = kg_facts.propose("default", "supply_chain", "MAT:A", "可替代", "MAT:B", "测试", 0.9)
    assert p["status"] == "draft"
    approved = await kg_facts.approve(p["id"], tenant_id="default")
    assert approved["status"] == "approved"
    assert "ENTITY:MAT:A" in calls.get("nodes", [])
    assert ("ENTITY:MAT:A", "ENTITY:MAT:B", "可替代") in calls.get("edges", [])


# ---------- P2-5 在线偏好学习 lite ----------
def test_preference_calibration_no_data():
    cal = preference_learning.preference_calibration("supply_chain")
    assert cal["verdict"] == "no_data"
    assert cal["approval_rate"] is None


def test_preference_calibration_trusted():
    for _ in range(6):
        experience.record_feedback("default", "supply_chain", "lock_alternative", "approved")
    cal = preference_learning.preference_calibration("supply_chain")
    assert cal["verdict"] == "trusted"
    assert cal["approval_rate"] == 1.0


def test_preference_calibration_needs_review():
    for _ in range(3):
        experience.record_feedback("default", "supply_chain", "lock_alternative", "rejected",
                                   context="越界", note="收紧")
    cal = preference_learning.preference_calibration("supply_chain")
    assert cal["verdict"] == "needs_review"
    assert cal["top_rejected_action"] == "lock_alternative"


# ---------- API 接线（ASGITransport，不触发 lifespan） ----------
@pytest.mark.asyncio
async def test_api_reflect_and_versions():
    from src.runtime.main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 初始无版本
        r0 = await client.get("/evolution/prompt-versions/supply_chain")
        assert r0.status_code == 200
        assert r0.json()["versions"] == []

        # 复盘（无失败案例 → source=none，生成 proposed 版本）
        r1 = await client.post("/evolution/reflect", json={"agent": "supply_chain"})
        assert r1.status_code == 200
        body = r1.json()
        assert body["status"] == "proposed"
        vid = body["version_id"]

        # 列出应有 1 个版本
        r2 = await client.get("/evolution/prompt-versions/supply_chain")
        assert len(r2.json()["versions"]) == 1

        # 审批通过
        r3 = await client.post(f"/evolution/prompt-versions/{vid}/approve")
        assert r3.status_code == 200
        assert r3.json()["status"] == "approved"

        # 偏好校准端点可用
        r4 = await client.get("/evolution/preference/supply_chain")
        assert r4.status_code == 200
