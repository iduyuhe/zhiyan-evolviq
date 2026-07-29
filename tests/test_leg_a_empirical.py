"""腿 A 实证回归测试：研究案例真实锚定推演层（消费真实公开披露 + 事实一致性自检）

验证：
1. case_telecom_2026 含真实 disclosure_facts 与 derived_insights
2. derived_insights 全部通过事实一致性自检（verified=True）
3. 「准且有价值」结论 ≥ 3 条
4. 匿名铁律：analyze 输出不得含真实锚定名
"""
import json

import pytest

from src.agents.case_curator.agent import case_curator_agent
from src.agents.industry_research.agent import industry_research_agent


@pytest.mark.asyncio
async def test_leg_a_disclosure_and_insights_present():
    case = case_curator_agent._get_case("case_telecom_2026")
    assert case, "案例 case_telecom_2026 应存在"
    facts = case.get("disclosure_facts")
    assert facts, "案例应包含真实 disclosure_facts"
    assert len(facts.get("facts", [])) >= 15, "披露事实应 ≥15 项"
    insights = case.get("derived_insights")
    assert insights and len(insights) >= 6, "应有 ≥6 条研究结论"


@pytest.mark.asyncio
async def test_leg_a_all_insights_verified():
    case = case_curator_agent._get_case("case_telecom_2026")
    facts = case["disclosure_facts"]
    insights = case["derived_insights"]
    verified = industry_research_agent._verify_insights(facts, insights)
    assert len(verified) == len(insights)
    assert all(x["verified"] for x in verified), f"存在未通过自检的结论: {verified}"


@pytest.mark.asyncio
async def test_leg_a_valuable_count_ge_3():
    case = case_curator_agent._get_case("case_telecom_2026")
    facts = case["disclosure_facts"]
    insights = case["derived_insights"]
    verified = industry_research_agent._verify_insights(facts, insights)
    valuable = [x for x in verified if x["value_judgment"] in ("high", "medium")]
    assert len(valuable) >= 3, f"准且有价值结论应 ≥3，实际 {len(valuable)}"


@pytest.mark.asyncio
async def test_leg_a_analyze_output_clean_and_verified():
    out = await industry_research_agent.analyze(
        "评估算力业务成为第二增长引擎的可持续性，以及毛利率阶段性承压对盈利质量的影响",
        case_id="case_telecom_2026",
    )
    assert out["status"] == "completed"
    assert out["mode"] == "research_case"
    # 匿名铁律：输出不得含真实锚定名
    dumped = json.dumps(out, ensure_ascii=False)
    assert "中兴通讯" not in dumped, "analyze 输出不得泄漏真实公司名"
    assert "000063" not in dumped, "analyze 输出不得泄漏股票代码"
    # 真实推演层生效
    assert out["calibration"]["verified_insight_count"] >= 6
    assert all(x["verified"] for x in out["derived_insights"])
