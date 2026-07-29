"""研究案例范式 Phase 1 测试（2026-07-29 杜总拍板执行）

覆盖：
- 注册表扩至 22 个 agent（含 industry_research / case_curator）
- 路由触发词命中两个新 agent
- industry_research 范式发动机：completed + 不外泄真实锚定名
- case_curator 案例库本体：案例列表 / 教学双版（external 视图无真名）
- 4 外圈 agent 支持 mode=research_case：research_case 下不写租户作用域记忆(atomic action 为空)
"""

import json

import pytest

from src.runtime.agent.router import AGENT_REGISTRY, execute_by_agent, route_goal

OUTER_RING = ("executive_cockpit", "supply_chain", "compliance_q", "cost_analysis")
LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte"]


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


# ===== 1. 注册表 =====

def test_registry_has_24_agents():
    assert len(AGENT_REGISTRY) == 24, f"注册表应为 24，实际 {len(AGENT_REGISTRY)}"
    assert "industry_research" in AGENT_REGISTRY
    assert "case_curator" in AGENT_REGISTRY
    assert "enterprise_onboarding" in AGENT_REGISTRY
    assert "compliance_reviewer" in AGENT_REGISTRY


def test_route_goal_triggers_new_agents():
    assert route_goal("请做一份通讯行业研究案例推演") == "industry_research"
    assert route_goal("汇总一下案例库并生成教学双版") == "case_curator"


# ===== 2. industry_research 范式发动机 =====

@pytest.mark.asyncio
async def test_industry_research_completed_no_leak():
    from src.agents.industry_research.agent import industry_research_agent

    result = await industry_research_agent.analyze("对通讯行业标杆企业做战略/供应链/合规/成本四维推演")
    assert result["status"] == "completed"
    assert result["mode"] == "research_case"
    assert result["case_id"] == "case_telecom_2026"
    # 🔴 匿名铁律：外发结果不得含真实锚定名
    _assert_no_leak(result, "industry_research")
    # outer_ring 四个外圈均已调度（成功或失败不破管）
    for ag in OUTER_RING:
        assert ag in result["outer_ring"]


# ===== 3. case_curator 案例库本体 =====

@pytest.mark.asyncio
async def test_case_curator_list_and_teaching_dual_version():
    from src.agents.case_curator.agent import case_curator_agent

    listed = await case_curator_agent.analyze("列出案例库")
    assert listed["status"] == "completed"
    assert listed["case_count"] >= 1
    _assert_no_leak(listed, "case_curator.list")

    dual = await case_curator_agent.analyze("生成教学双版")
    assert dual["status"] == "completed"
    assert dual["dual_version_count"] >= 1
    # 🔴 external 视图严禁含真名；internal 视图可含
    seen_ids = set()
    for d in dual["dual_versions"]:
        ext = json.dumps(d["teaching_external"], ensure_ascii=False)
        for tok in LEAK_TOKENS:
            assert tok not in ext, f"❌ teaching_external 外泄真实锚定名 {tok!r}"
        # internal 视图与 external 同 case_id 且含 real_anchor（双版对称）
        assert d["teaching_internal"]["case_id"] == d["teaching_external"]["case_id"]
        assert d["teaching_internal"].get("real_anchor")
        seen_ids.add(d["teaching_internal"]["case_id"])
    # 多案例时代（2026-07-29 起）：通讯首例必在，其余案例并存
    assert "case_telecom_2026" in seen_ids


# ===== 4. 4 外圈 agent 支持 mode=research_case =====

@pytest.mark.asyncio
@pytest.mark.parametrize("ag", OUTER_RING)
async def test_outer_ring_research_mode_gates_tenant_actions(ag):
    result = await execute_by_agent(
        ag, f"{ag} 研究案例推演", mode="research_case", case_id="case_telecom_2026"
    )
    assert result["mode"] == "research_case", f"{ag} 应回传 mode=research_case"
    assert result["case_id"] == "case_telecom_2026"
    # executive/cost/compliance 在 research_case 下不得写租户作用域记忆(atomic action 为空)
    if ag in ("executive_cockpit", "cost_analysis", "compliance_q"):
        assert result.get("actions_taken") == [], f"{ag} research_case 下不应自动写租户行动"
    _assert_no_leak(result, f"{ag}.research_case")
