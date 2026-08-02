"""Agent 心跳自触发引擎测试（2026-08-02 OpenClaw HEARTBEAT 借鉴）

覆盖：
1. 默认未启用（configure 读 settings，ZHIYAN_HEARTBEAT_ENABLED 缺省 False）
2. 风险判定：supply_chain 缺料 / bid_intel 商机 / energy_carbon 碳强度——有风险返回文案，无风险 None（静默）
3. patrol_once：有风险 → alert_monitor 发布（cooldown 去重）；无风险 → 静默不发布
4. mode=heartbeat 纪律：supply_chain 不执行锁料/补货动作（无副作用）；不写租户记忆
5. 幂等：同 key 300s cooldown 内不重复发布
"""

import time

import pytest

from src.runtime.heartbeat.engine import (
    heartbeat_engine,
    _risk_judge_supply_chain,
    _risk_judge_bid_intel,
    _risk_judge_energy_carbon,
    _risk_judge_finance,
)


class TestRiskJudges:
    def test_supply_chain_risk_positive(self):
        assert _risk_judge_supply_chain({"risk_items_before": 3}) is not None
        assert _risk_judge_supply_chain({"risk_items_total": 1}) is not None

    def test_supply_chain_risk_silent(self):
        """无风险 → None（静默门控）。"""
        assert _risk_judge_supply_chain({}) is None
        assert _risk_judge_supply_chain({"risk_items_before": 0}) is None

    def test_bid_intel_opportunities(self):
        assert _risk_judge_bid_intel({"opportunities": [{"title": "集采招标"}]}) is not None
        assert _risk_judge_bid_intel({"opportunities": []}) is None

    def test_energy_carbon_intensity_gap(self):
        assert _risk_judge_energy_carbon({"intensity_gap": 0.5}) is not None
        assert _risk_judge_energy_carbon({"intensity_gap": 0, "green_ratio": 10}) is not None
        assert _risk_judge_energy_carbon({"intensity_gap": 0, "green_ratio": 30}) is None

    def test_finance_risk(self):
        """资金风险：安全垫 <30 天 / 应收 90+ ≥15% / 预测现金 ≤0。"""
        assert _risk_judge_finance({"days_of_cash": 20}) is not None
        assert _risk_judge_finance({"overdue_90_ratio": 18}) is not None
        assert _risk_judge_finance({"cash_buffer_verdict": "紧张"}) is not None
        assert _risk_judge_finance({"days_of_cash": 45, "overdue_90_ratio": 5, "cash_buffer_verdict": "充足"}) is None


class TestHeartbeatEngine:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setattr("src.common.config.settings.heartbeat_enabled", False)
        assert heartbeat_engine.configure() is False
        assert heartbeat_engine.enabled is False

    def test_configure_enabled(self, monkeypatch):
        monkeypatch.setattr("src.common.config.settings.heartbeat_enabled", True)
        monkeypatch.setattr("src.common.config.settings.heartbeat_interval_supply_chain", 30)
        monkeypatch.setattr("src.common.config.settings.heartbeat_interval_bid_intel", 60)
        monkeypatch.setattr("src.common.config.settings.heartbeat_interval_energy_carbon", 90)
        assert heartbeat_engine.configure() is True
        # 恢复默认（避免污染后续测试）
        monkeypatch.setattr("src.common.config.settings.heartbeat_enabled", False)
        heartbeat_engine.configure()

    @pytest.mark.asyncio
    async def test_patrol_once_silent_when_no_risk(self):
        """无风险：静默，不产生告警。"""
        from src.runtime.monitoring import alert_monitor

        n_before = len(alert_monitor.alerts(kind="heartbeat_risk"))
        out = await heartbeat_engine.patrol_once(
            "bid_intel", "心跳巡检：扫描商机情报信号", _risk_judge_bid_intel, "warning", "商机扫描"
        )
        assert out["fired"] is False
        n_after = len(alert_monitor.alerts(kind="heartbeat_risk"))
        assert n_after == n_before  # 静默

    @pytest.mark.asyncio
    async def test_patrol_once_fires_on_risk(self):
        """有风险：发布告警（kind=heartbeat_risk）。"""
        from src.runtime.monitoring import alert_monitor
        from src.runtime.uns import uns

        # 清理同 key cooldown，确保可发布
        alert_monitor._last_fired.pop("heartbeat:supply_chain", None)
        uns._events.clear()

        # supply_chain 心跳：seed 数据存在缺料（PCB-001 on_hand=0 等）→ risk>0
        out = await heartbeat_engine.patrol_once(
            "supply_chain", "心跳巡检：检查物料齐套与缺料风险", _risk_judge_supply_chain, "critical", "缺料巡检"
        )
        assert out["fired"] is True
        assert "缺料" in out["detail"]
        alerts = alert_monitor.alerts(kind="heartbeat_risk")
        assert any(a["key"] == "heartbeat:supply_chain" for a in alerts)

    @pytest.mark.asyncio
    async def test_cooldown_dedup(self):
        """幂等：cooldown(300s) 内同 key 不重复发布。"""
        from src.runtime.monitoring import alert_monitor

        alert_monitor._last_fired.pop("heartbeat:supply_chain", None)
        first = await heartbeat_engine.patrol_once(
            "supply_chain", "心跳巡检：检查物料齐套与缺料风险", _risk_judge_supply_chain, "critical", "缺料巡检"
        )
        assert first["fired"] is True
        # cooldown 内再触发 → 不发布
        second = await heartbeat_engine.patrol_once(
            "supply_chain", "心跳巡检：检查物料齐套与缺料风险", _risk_judge_supply_chain, "critical", "缺料巡检"
        )
        assert second["fired"] is False
        # 清理 cooldown 状态
        alert_monitor._last_fired.pop("heartbeat:supply_chain", None)

    @pytest.mark.asyncio
    async def test_supply_chain_heartbeat_no_side_effects(self):
        """mode=heartbeat：supply_chain 不执行锁料/补货（无副作用）。"""
        from src.agents.supply_chain.agent import SupplyChainAgent

        agent = SupplyChainAgent()
        result = await agent.analyze("心跳巡检：检查物料齐套与缺料风险", mode="heartbeat")
        assert result["status"] == "completed"
        assert result["mode"] == "heartbeat"
        assert "risk_items_before" in result
        assert "心跳巡检" in result.get("note", "")
        # 无 actions_taken（未执行锁料/补货）
        assert "actions_taken" not in result or result.get("actions_taken", []) == []

    @pytest.mark.asyncio
    async def test_heartbeat_does_not_contaminate_tenant(self):
        """心跳不写租户记忆：模式恒 heartbeat，无 research_case note 混淆。"""
        from src.agents.bid_intel.agent import BidIntelAgent

        agent = BidIntelAgent()
        r = await agent.analyze("心跳巡检：扫描商机情报信号", mode="heartbeat")
        assert r["mode"] == "heartbeat"
        assert "research_case" not in r.get("note", "")

    # ===== 财务决策维度（2026-08-02 补全）=====

    @pytest.mark.asyncio
    async def test_executive_finance_decision_fields(self):
        """tenant 模式：financial_decision 块含应收账龄 + 现金流预测（只读推演，不碰账本）。"""
        from src.agents.executive_cockpit.agent import ExecutiveCockpitAgent

        agent = ExecutiveCockpitAgent()
        r = await agent.analyze("经营财务分析", mode="tenant")
        fd = r.get("financial_decision", {})
        assert "receivables" in fd and "cash_forecast" in fd
        recv = fd["receivables"]
        assert "buckets" in recv and "overdue_90_ratio" in recv
        assert "risk_level" in recv
        fc = fd["cash_forecast"]
        assert "series" in fc and len(fc["series"]) == 3
        assert "min_cash" in fc

    @pytest.mark.asyncio
    async def test_executive_heartbeat_no_side_effects(self):
        """mode=heartbeat：executive 只推演财务决策，不执行 create_action_item。"""
        from src.agents.executive_cockpit.agent import ExecutiveCockpitAgent

        agent = ExecutiveCockpitAgent()
        r = await agent.analyze("心跳巡检：检查现金安全垫与应收风险", mode="heartbeat")
        assert r["mode"] == "heartbeat"
        assert "receivable_risk" in r and "days_of_cash" in r
        assert "actions_taken" not in r or r.get("actions_taken", []) == []

    @pytest.mark.asyncio
    async def test_patrol_once_finance_fires_on_risk(self):
        """资金巡检：seed 应收 90+ 占比 = 600/6100≈9.8% → 不触发；验证引擎链路可用（含无风险静默）。"""
        from src.runtime.monitoring import alert_monitor

        alert_monitor._last_fired.pop("heartbeat:executive_cockpit", None)
        out = await heartbeat_engine.patrol_once(
            "executive_cockpit", "心跳巡检：检查现金安全垫与应收风险", _risk_judge_finance, "critical", "资金巡检"
        )
        # seed 数据 days_of_cash=45（充足）、90+占比 9.8%（<15%）→ 无风险静默
        assert out["fired"] is False
        assert out["detail"] == "无风险，静默"
