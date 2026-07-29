"""腿 B 首客 P3：试点企业(中芯国际·内部锚定) + 场景 A=设备健康/能耗孪生（2026-07-29 杜总定调）

覆盖：
- case_semicon_2026 入库 + pilot_scenario 挂接（场景 A，agents=pm_maintenance/energy_carbon）
- industry_research 半导体案例推演：pilot_ring 试点管线 + pilot_hooks（网关 simulated/北极星埋点）
- research_case 纪律：pm_maintenance/energy_carbon 在匿名模式 actions_taken 恒空、不读租户孪生
- ANON_SCRUB_MAP 递归擦洗：SMIC/中芯/688981 等真名片段零外泄
- compliance_reviewer 合规闸门全链路 passed

🔴 匿名铁律：LEAK_TOKENS（含第 2 案例半导体真名片段）对一切外发结果断言零真名。
🔴 杜总铁律①：外部接口（网关/北极星）只建钩子不实测——测试仅断言钩子就位。
"""

import json

import pytest

# 两案例真名片段全集（与 compliance_reviewer.LEAK_TOKENS 保持一致）
LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte",
               "中芯", "688981", "00981", "SMIC", "smic"]

SEMICON_CASE_ID = "case_semicon_2026"


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


# ---------- 案例库：半导体案例入库 + 试点场景挂接 ----------

@pytest.mark.asyncio
async def test_semicon_case_in_store_with_pilot_scenario():
    from src.agents.case_curator.agent import case_curator_agent

    case_curator_agent._ensure_seed()
    res = await case_curator_agent.analyze(f"案例 {SEMICON_CASE_ID} 详情")
    assert res["status"] == "completed"
    c = res["case"]
    assert c["case_id"] == SEMICON_CASE_ID
    # 🔴 对外视图不含 real_anchor
    assert "real_anchor" not in c
    _assert_no_leak(res, "case_curator.semicon_detail")
    # 试点场景挂接（场景 A：设备健康/能耗孪生）
    ps = c.get("pilot_scenario")
    assert ps, "❌ 半导体案例缺 pilot_scenario（腿 B 首客 P3 未挂接）"
    assert ps["scenario"] == "A"
    assert set(ps["agents"]) == {"pm_maintenance", "energy_carbon"}


@pytest.mark.asyncio
async def test_semicon_case_incremental_seed_preserves_existing():
    """种子增量升级：_ensure_seed 不覆盖已有案例，两案例并存。"""
    from src.agents.case_curator.agent import case_curator_agent

    case_curator_agent._ensure_seed()
    listed = await case_curator_agent.analyze("列出案例库")
    ids = {c["case_id"] for c in listed["cases"]}
    assert "case_telecom_2026" in ids
    assert SEMICON_CASE_ID in ids


def test_anon_scrub_map_ordering():
    """ANON_SCRUB_MAP 长 token 在前（防子串错洗，如 中兴通讯 先于 中兴）。"""
    from src.agents.case_curator.agent import ANON_SCRUB_MAP

    tokens = [t for t, _ in ANON_SCRUB_MAP]
    for i, a in enumerate(tokens):
        for j, b in enumerate(tokens):
            if i != j and a != b and a in b:
                assert j < i, f"❌ 短 token {a!r} 排在其超串 {b!r} 之前，将导致子串错洗"


# ---------- research_case 纪律：场景 agent 匿名模式 ----------

@pytest.mark.asyncio
async def test_pm_maintenance_research_case_discipline():
    from src.agents.pm_maintenance.agent import pm_agent

    res = await pm_agent.analyze("设备健康推演", mode="research_case", case_id=SEMICON_CASE_ID)
    assert res["status"] == "completed"
    assert res["mode"] == "research_case"
    # 🔴 原子行动恒空（不落工单/不写租户记忆）；推演建议保留在 actions_proposed
    assert res["actions_taken"] == []
    assert "actions_proposed" in res


@pytest.mark.asyncio
async def test_energy_carbon_research_case_discipline():
    from src.agents.energy_carbon.agent import energy_carbon_agent

    res = await energy_carbon_agent.analyze("能耗孪生推演", mode="research_case", case_id=SEMICON_CASE_ID)
    assert res["status"] == "completed"
    assert res["mode"] == "research_case"
    # 🔴 原子行动恒空（不落节能任务）
    assert res["actions_taken"] == []
    # 🔴 私域/公开边界红线：不读租户孪生流
    twin = res["twin_context"]
    assert twin["enabled"] is False
    assert "research_case" in (twin.get("skipped_reason") or "")


@pytest.mark.asyncio
async def test_pm_energy_tenant_mode_unchanged():
    """tenant 模式行为不回归：actions_taken 照常生成（向后兼容）。"""
    from src.agents.pm_maintenance.agent import pm_agent

    res = await pm_agent.analyze("检查全部设备健康")
    assert res["status"] == "completed"
    assert "actions_proposed" not in res  # tenant 模式无该字段
    assert "mode" not in res


# ---------- 范式发动机：半导体案例试点管线 ----------

@pytest.mark.asyncio
async def test_industry_research_semicon_pilot_ring():
    from src.agents.industry_research.agent import industry_research_agent

    res = await industry_research_agent.analyze(
        "对半导体晶圆代工标杆企业做设备健康/能耗孪生试点推演",
        case_id=SEMICON_CASE_ID,
    )
    assert res["status"] == "completed"
    assert res["mode"] == "research_case"
    assert res["case_id"] == SEMICON_CASE_ID
    # 🔴 全量零泄漏（含 SMIC/中芯/688981 等第 2 案例真名片段）
    _assert_no_leak(res, "industry_research.semicon")
    # 试点管线挂接：场景 A 两 agent 均在 pilot_ring
    pilot = res.get("pilot_ring")
    assert pilot, "❌ pilot_ring 缺失（试点管线未挂接）"
    assert set(pilot.keys()) == {"pm_maintenance", "energy_carbon"}
    for ag, r in pilot.items():
        assert r.get("mode") == "research_case", f"{ag} 未打 research_case 标"
        assert r.get("actions_taken") in (None, []), f"{ag} actions_taken 非空"
    # 试点场景块（匿名安全）
    assert res["pilot_scenario"]["scenario"] == "A"
    # 🔴 杜总铁律①：外部接口只建钩子不实测——断言钩子就位即可
    hooks = res.get("pilot_hooks")
    assert hooks and hooks["gateway_mode"] == "simulated"
    assert "record_decision_realization" in hooks["north_star"]


@pytest.mark.asyncio
async def test_industry_research_semicon_insights_verified():
    """半导体案例 6 条推演结论全部通过事实一致性自检（key_figures 溯源披露事实）。"""
    from src.agents.industry_research.agent import industry_research_agent

    res = await industry_research_agent.analyze("半导体研究案例推演", case_id=SEMICON_CASE_ID)
    insights = res.get("derived_insights", [])
    assert len(insights) >= 6
    for ins in insights:
        assert ins["verified"], f"❌ 结论未通过事实自检：{ins.get('claim', '')[:40]} 缺 {ins['unverified_figures']}"
    _assert_no_leak(insights, "industry_research.semicon_insights")


@pytest.mark.asyncio
async def test_industry_research_telecom_case_no_pilot_ring():
    """首例通讯案例无 pilot_scenario → 不产生 pilot_ring（管线按案例声明驱动）。"""
    from src.agents.industry_research.agent import industry_research_agent

    res = await industry_research_agent.analyze("通讯行业研究案例推演", case_id="case_telecom_2026")
    assert res["status"] == "completed"
    assert "pilot_ring" not in res
    _assert_no_leak(res, "industry_research.telecom")


# ---------- 合规闸门：全链路复核 ----------

@pytest.mark.asyncio
async def test_compliance_reviewer_covers_semicon_pilot():
    from src.agents.compliance_reviewer.agent import LEAK_TOKENS as CR_TOKENS
    from src.agents.compliance_reviewer.agent import compliance_reviewer_agent

    # 闸门 token 集必须覆盖第 2 案例真名片段
    for tok in ("中芯", "688981", "00981", "SMIC", "smic"):
        assert tok in CR_TOKENS, f"❌ 合规闸门缺真名片段 {tok!r}"

    res = await compliance_reviewer_agent.analyze("全链路合规复核")
    assert res["status"] == "completed"
    assert res["passed"] is True, f"❌ 合规闸门未通过：{res['violations']}"
    # 半导体案例 + 试点管线检查项已纳入
    targets = {(c["check"], c["target"]) for c in res["checks"]}
    assert ("zero_leak", "industry_research(semicon)") in targets
    assert ("pilot_ring_discipline", "pilot_ring") in targets
