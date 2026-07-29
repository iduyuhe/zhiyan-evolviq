"""Phase 3.1 案例库多案例横向扩展（#398，2026-07-29）

覆盖：
- case_curator 多案例能力：列表(含 active_case_id) / 搜索 / 按 case_id 取详情
- industry_research 支持指定 case_id 推演（默认用案例库 active 案例）
- 范围纪律：只做通讯单案例（real_anchor=中兴仅在 internal 视图/内部变量，零外泄）
- 对外视图（列表/搜索/详情）绝不含 real_anchor 真名

🔴 匿名铁律：LEAK_TOKENS 对一切外发结果断言零真名。
"""

import json

import pytest

from src.runtime.agent.router import AGENT_REGISTRY

LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte"]

DEFAULT_CASE_ID = "case_telecom_2026"


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


def test_case_curator_in_registry():
    assert "case_curator" in AGENT_REGISTRY


@pytest.mark.asyncio
async def test_case_curator_list_has_active_case_id():
    from src.agents.case_curator.agent import case_curator_agent

    listed = await case_curator_agent.analyze("列出案例库")
    assert listed["status"] == "completed"
    assert listed["case_count"] >= 1
    assert listed["active_case_id"] == DEFAULT_CASE_ID
    # 列表视图不含 real_anchor
    for c in listed["cases"]:
        assert "real_anchor" not in c
    _assert_no_leak(listed, "case_curator.list")


@pytest.mark.asyncio
async def test_case_curator_search_by_keyword():
    from src.agents.case_curator.agent import case_curator_agent

    res = await case_curator_agent.analyze("搜索通讯行业的研究案例")
    assert res["status"] == "completed"
    assert res["match_count"] >= 1
    ids = {c["case_id"] for c in res["cases"]}
    assert DEFAULT_CASE_ID in ids
    # 🔴 搜索结果视图不含真名
    _assert_no_leak(res, "case_curator.search")


@pytest.mark.asyncio
async def test_case_curator_get_by_case_id():
    from src.agents.case_curator.agent import case_curator_agent

    res = await case_curator_agent.analyze(f"案例 {DEFAULT_CASE_ID} 详情")
    assert res["status"] == "completed"
    assert res["case"]["case_id"] == DEFAULT_CASE_ID
    # 🔴 单案例详情（对外视图）不含 real_anchor
    assert "real_anchor" not in res["case"]
    _assert_no_leak(res, "case_curator.detail")


@pytest.mark.asyncio
async def test_case_curator_unknown_case_id_graceful():
    from src.agents.case_curator.agent import case_curator_agent

    # 不存在的 case_id → 退回列表（不破管）
    res = await case_curator_agent.analyze("案例 case_not_exist_999 详情")
    assert res["status"] == "completed"
    assert "cases" in res  # 退回列表视图


@pytest.mark.asyncio
async def test_industry_research_explicit_case_id():
    from src.agents.industry_research.agent import industry_research_agent

    res = await industry_research_agent.analyze(
        "对通讯行业标杆企业做战略/供应链/合规/成本四维推演",
        case_id=DEFAULT_CASE_ID,
    )
    assert res["status"] == "completed"
    assert res["mode"] == "research_case"
    assert res["case_id"] == DEFAULT_CASE_ID
    _assert_no_leak(res, "industry_research.explicit_case_id")
    for ag in ("executive_cockpit", "supply_chain", "compliance_q", "cost_analysis"):
        assert ag in res["outer_ring"]


@pytest.mark.asyncio
async def test_industry_research_default_uses_active_case():
    from src.agents.case_curator.agent import case_curator_agent
    from src.agents.industry_research.agent import industry_research_agent

    active = case_curator_agent._active_case_id()
    res = await industry_research_agent.analyze("做一份通讯行业研究案例推演")
    assert res["status"] == "completed"
    assert res["case_id"] == active
    _assert_no_leak(res, "industry_research.default_case")
