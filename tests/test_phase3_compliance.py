"""Phase 3.2 合规闸门 Agent（#399，2026-07-29）

覆盖：
- 注册表含 compliance_reviewer（第 25 个 agent）
- route_goal("合规审查研究案例输出") → compliance_reviewer（且普通「合规」仍归 compliance_q）
- 合规复核通过：零泄漏 + 双版边界 + research_case 纪律 全部达标
- 合规 Agent 自身输出零真名外泄

范围纪律：只做通讯单案例；compliance_reviewer 仅做静态合规复核，不新增任何真实锚定数据。
"""

import json

import pytest

from src.runtime.agent.router import AGENT_REGISTRY, route_goal

LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte"]


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


def test_registry_has_compliance_reviewer():
    assert "compliance_reviewer" in AGENT_REGISTRY, "注册表须含 compliance_reviewer"
    assert len(AGENT_REGISTRY) == 25


def test_route_goal_compliance_review():
    assert route_goal("请对研究案例输出做合规审查") == "compliance_reviewer"
    assert route_goal("零泄漏检查行业研究双版") == "compliance_reviewer"


def test_route_goal_plain_compliance_still_compliance_q():
    # 普通「合规」不应被合规闸门截获，仍归质量合规 agent
    assert route_goal("帮我做一下 iso 质量体系合规") == "compliance_q"


@pytest.mark.asyncio
async def test_compliance_review_passes():
    from src.agents.compliance_reviewer.agent import compliance_reviewer_agent

    res = await compliance_reviewer_agent.analyze("复核研究案例产出的匿名/真名边界与零泄漏")
    assert res["status"] == "completed"
    assert res["passed"] is True, f"合规复核应通过，实际违规：{res['violations']}"
    assert res["violation_count"] == 0
    # 三项检查齐备且全过
    check_names = {c["check"] for c in res["checks"]}
    assert {"zero_leak", "research_case_discipline", "dual_version_boundary"} <= check_names
    for c in res["checks"]:
        assert c["passed"] is True
    # 🔴 合规 Agent 自身输出零真名
    _assert_no_leak(res, "compliance_reviewer")


@pytest.mark.asyncio
async def test_compliance_review_detects_leak_in_external():
    """构造一个 teaching_external 含真名的案例，合规闸门应识别为违规。"""
    from src.agents.compliance_reviewer.agent import compliance_reviewer_agent

    # 直接调用内部检查方法（不依赖真实案例库被污染）
    fake_dual = {
        "status": "completed",
        "dual_versions": [
            {
                "teaching_external": {"case_id": "case_x", "subject_anon": "某某公司", "real_anchor": "中兴通讯（000063.SZ）"},
                "teaching_internal": {"case_id": "case_x", "real_anchor": "中兴通讯（000063.SZ）"},
            }
        ],
    }
    violations = []
    chk = compliance_reviewer_agent._check_dual_version_boundary(fake_dual, violations)
    assert chk["passed"] is False
    assert violations, "应检出 external 含真名"
    assert any("external 含真名" in v["detail"] for v in violations)
