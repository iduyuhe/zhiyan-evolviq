"""bid_intel 商机情报 Agent —— 第 25 个 Agent（2026-08-02 杜总拍板扩边缘，营销向实体化）

覆盖：
1. AGENT_REGISTRY 含 bid_intel（第 25 个 agent）
2. route_goal 触发词（投标/标前/赢单/商机/招投标/客户声音）→ bid_intel；不抢「成本/报价」
3. analyze 输出结构（opportunities / win_probability / pricing_strategy / bid_review）
4. 客户声音信号 → 商机机会纳入（env_context 通道级）
5. actions_taken 恒空（🔴 人留终审：情报分析不自动执行商务动作）
6. research_case 模式：不写租户记忆 + note 标注 + 零真名
7. AuthBoundary 存在（ab-bid-intel-default，auto_execute 为空=商务动作须审批）
8. 权限模板：FINANCE_CONTROLLER 可见 bid_intel；PLANT_MANAGER 全放行覆盖
9. 路由顺序铁律：「报价」归 cost_analysis，不抢
"""

import json

import pytest

from src.runtime.agent.router import AGENT_REGISTRY, route_goal, get_agent

# 🔴 匿名铁律：真实锚定名片段，任何外部结果都不得含
LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte"]


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


# ============ 1. 注册与路由 ============


class TestRegistry:
    def test_bid_intel_registered(self):
        assert "bid_intel" in AGENT_REGISTRY
        module_path, singleton = AGENT_REGISTRY["bid_intel"]
        assert module_path == "src.agents.bid_intel.agent"
        assert singleton == "bid_intel_agent"

    def test_route_goal_triggers_bid_intel(self):
        assert route_goal("评估这批集采项目的投标赢单概率") == "bid_intel"
        assert route_goal("做标前评审与竞品对标") == "bid_intel"
        assert route_goal("扫描近期商机与客户声音信号") == "bid_intel"
        assert route_goal("列出招投标机会清单") == "bid_intel"
        assert route_goal("win rate analysis for the tender") == "bid_intel"

    def test_route_goal_does_not_steal_cost_quote(self):
        """顺序铁律：「报价/成本」归 cost_analysis，bid_intel 不抢。"""
        assert route_goal("分析制造成本与报价底线") == "cost_analysis"
        assert route_goal("毛利与单位成本核算") == "cost_analysis"


# ============ 2. Agent 功能 ============


@pytest.fixture(autouse=True)
def _clean_uns():
    from src.runtime.uns import uns
    from src.runtime.env_perception import env_review

    uns._events.clear()
    env_review.clear()
    yield
    uns._events.clear()
    env_review.clear()


class TestBidIntelAgent:
    @pytest.mark.asyncio
    async def test_analyze_structure(self):
        agent = get_agent("bid_intel")
        r = await agent.analyze("投标标前评审", mode="tenant")
        assert r["status"] == "completed"
        assert "summary" in r
        assert isinstance(r["opportunities"], list)
        assert isinstance(r["win_probability"], dict)
        assert "score" in r["win_probability"] and "grade" in r["win_probability"]
        assert isinstance(r["pricing_strategy"], dict)
        assert isinstance(r["bid_review"], list)
        assert isinstance(r["recommendations"], list)

    @pytest.mark.asyncio
    async def test_actions_taken_always_empty(self):
        """🔴 人留终审：情报分析不自动执行商务动作。"""
        agent = get_agent("bid_intel")
        r = await agent.analyze("投标赢单概率", mode="tenant")
        assert r["actions_taken"] == []

    @pytest.mark.asyncio
    async def test_customer_voice_signal_feeds_opportunities(self):
        from src.runtime.env_sources.customer_voice_source import CustomerVoiceSource

        src = CustomerVoiceSource()
        src.publish_signal({
            "title": "某运营商发布新一轮集采招标（测试信号）",
            "content": "客户集采招标强调低时延与自主可控，交付窗口 12 个月。",
            "category": "customer_voice",
            "entities": ["CUS:运营商", "POLICY:自主可控"],
            "url": "https://example.com/tender",
        })
        agent = get_agent("bid_intel")
        r = await agent.analyze("扫描商机", mode="tenant")
        assert any("集采招标" in o["title"] for o in r["opportunities"])
        # 信号溯源
        assert r["env_signal_count"] >= 1

    @pytest.mark.asyncio
    async def test_research_case_mode_no_tenant_side_effects(self):
        agent = get_agent("bid_intel")
        r = await agent.analyze("投标赢单概率", mode="research_case", case_id="case_telecom_2026")
        assert r["mode"] == "research_case"
        assert "研究案例模式" in r.get("note", "")
        assert r["actions_taken"] == []
        _assert_no_leak(r, "research_case analyze")

    @pytest.mark.asyncio
    async def test_win_probability_deterministic(self):
        """确定性规则：同输入同输出（非黑盒）。"""
        agent = get_agent("bid_intel")
        r1 = await agent.analyze("投标标前评审", mode="tenant")
        r2 = await agent.analyze("投标标前评审", mode="tenant")
        assert r1["win_probability"]["score"] == r2["win_probability"]["score"]
        assert 20 <= r1["win_probability"]["score"] <= 95


# ============ 3. 权限边界 ============


class TestAuthorization:
    def test_auth_boundary_exists_with_no_auto_execute(self):
        from src.runtime.core.authorization import authorization

        b = authorization.get_for_agent("bid_intel")
        assert b is not None
        assert b.agent == "bid_intel"
        # 🔴 人留终审：不自动执行任何商务动作
        assert b.auto_execute_actions == []
        assert "submit_bid" in b.require_approval_actions

    def test_finance_controller_can_see_bid_intel(self):
        from src.presets.permission_templates import scope_for_business_role

        scope = scope_for_business_role("finance_controller")
        assert "bid_intel" in scope["allowed_agents"]
        assert "bid_intel" in scope["read_only_agents"]

    def test_plant_manager_star_covers_bid_intel(self):
        from src.presets.permission_templates import scope_for_business_role

        scope = scope_for_business_role("plant_manager")
        assert scope["allowed_agents"] == ["*"]
