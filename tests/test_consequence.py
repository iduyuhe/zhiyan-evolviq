"""v22 蓝弧闭环单元测试

验证：
1. ConsequenceTracker.record() 校验预期 vs 实际，返回正确 match 结果
2. 预期后果匹配 → 提升 KG 置信度 + 经验库已记录
3. 预期后果不匹配 → 降低 KG 置信度；低于阈值 → 自动纠错 draft（自进化燃料）
4. 无预期注册的后果：记录但不校验（轨迹完整性）
5. 方向性预期校验（_expect_decrease / _expect_increase）
6. 数值容差校验（5% 浮点容差）
7. UNS gateway 通道含 action_id 自动触发后果捕获
8. 查询与统计
9. 韧性降级：KG 不可达时经验库仍记录
"""

import pytest
import time

from src.runtime.consequence import ConsequenceTracker, init_consequence
from src.runtime.evolution.kg_facts import kg_facts
from src.runtime.experience import experience
from src.runtime.uns import uns, CHANNEL_GATEWAY, CHANNEL_SYSTEM


@pytest.fixture
def cleared():
    """清空所有单例的可变状态（保留 UNS 订阅者）。"""
    consequence = ConsequenceTracker()
    # 替换全局单例为干净实例（仅在测试范围内，通过模拟实现）
    import src.runtime.consequence as cmod
    old = cmod.consequence
    cmod.consequence = consequence
    kg_facts._proposals.clear()
    experience._records.clear()
    uns._events.clear()
    yield consequence
    kg_facts._proposals.clear()
    experience._records.clear()
    uns._events.clear()
    cmod.consequence = old


class TestBasic:

    def test_record_match(self):
        ct = ConsequenceTracker()
        ct.expect_outcome("act-001", "energy_carbon", {"energy_kwh": 100.0})
        rec = ct.record("act-001", {"energy_kwh": 100.0})
        assert rec is not None
        assert rec.match is True
        assert rec.action_id == "act-001"
        assert rec.agent == "energy_carbon"

    def test_record_mismatch(self):
        ct = ConsequenceTracker()
        ct.expect_outcome("act-002", "energy_carbon", {"energy_kwh": 100.0})
        rec = ct.record("act-002", {"energy_kwh": 120.0})  # >5% off → mismatch
        assert rec is not None
        assert rec.match is False

    def test_float_tolerance(self):
        """容差 5%：103.5 应在 100.0 的 5% 以内（+3.5%）。"""
        ct = ConsequenceTracker()
        ct.expect_outcome("act-003", "agent", {"key": 100.0})
        rec = ct.record("act-003", {"key": 103.5})
        assert rec.match is True

    def test_value_out_of_tolerance(self):
        """超过 5% 容差应 mismatch。"""
        ct = ConsequenceTracker()
        ct.expect_outcome("act-004", "agent", {"key": 100.0})
        rec = ct.record("act-004", {"key": 105.5})  # +5.5%
        assert rec.match is False

    def test_expect_decrease(self):
        """方向性预期：能耗应下降。"""
        ct = ConsequenceTracker()
        ct.expect_outcome("act-005", "energy_carbon", {
            "_expect_decrease": 150.0, "_target_key": "energy_kwh",
        })
        rec = ct.record("act-005", {"energy_kwh": 140.0})
        assert rec.match is True

    def test_expect_decrease_fail(self):
        ct = ConsequenceTracker()
        ct.expect_outcome("act-006", "energy_carbon", {
            "_expect_decrease": 150.0, "_target_key": "energy_kwh",
        })
        rec = ct.record("act-006", {"energy_kwh": 160.0})
        assert rec.match is False

    def test_no_pending_record(self):
        """无预期注册的后果 → 记录但不校验 match。"""
        ct = ConsequenceTracker()
        rec = ct.record("act-orphan", {"temp": 42.0})
        assert rec is not None
        assert rec.match is False
        assert rec.match_detail["reason"] == "no_predicted_registered"

    def test_stats(self):
        ct = ConsequenceTracker()
        ct.expect_outcome("a1", "x", {"v": 1.0})
        ct.expect_outcome("a2", "x", {"v": 1.0})
        ct.record("a1", {"v": 1.0})   # match
        ct.record("a2", {"v": 2.0})   # mismatch
        ct.record("a3", {"v": 1.0})   # no pending
        s = ct.stats()
        assert s["total_consequences"] == 3
        assert s["validated"] == 1
        assert s["contradicted"] == 2  # a2 mismatch + a3 no-pending
        assert s["pending_outcomes"] == 0


class TestCognitiveLayerFeedback:

    def test_validate_bumps_confidence(self, cleared):
        """后果校验 match → KG 事实置信度提升 + 状态变为 validated。"""
        fact = kg_facts.propose("default", "energy_carbon", "EMP:zhang", "tacit_judges", "风险", confidence=0.60)
        kid = fact["id"]
        ct = ConsequenceTracker()
        ct.expect_outcome("act-010", "energy_carbon", {"risk": 1}, linked_fact_id=kid)
        ct.record("act-010", {"risk": 1.0})

        updated = kg_facts.get(kid)
        assert updated is not None
        assert updated["confidence"] > 0.60  # bumped
        assert updated["status"] == "validated"

    def test_mismatch_lowers_confidence(self, cleared):
        """后果不匹配 → KG 置信度降低 + 状态变为 needs_review。"""
        fact = kg_facts.propose("default", "energy_carbon", "EMP:zhang", "tacit_judges", "风险", confidence=0.60)
        kid = fact["id"]
        ct = ConsequenceTracker()
        ct.expect_outcome("act-011", "energy_carbon", {"risk": 1}, linked_fact_id=kid)
        ct.record("act-011", {"risk": 5.0})  # mismatch

        updated = kg_facts.get(kid)
        assert updated is not None
        assert updated["confidence"] < 0.60
        assert updated["status"] == "needs_review"

    def test_correction_proposed_when_below_threshold(self, cleared):
        """置信度低于 0.30 → 自动提议纠错 draft。"""
        fact = kg_facts.propose("default", "energy_carbon", "EMP:li", "tacit_judges", "无风险", confidence=0.40)
        kid = fact["id"]
        ct = ConsequenceTracker()
        # 连续两次 mismatch 使置信度降到 0.40-0.15=0.25 < 0.30
        ct.expect_outcome("act-012", "energy_carbon", {"risk": 0}, linked_fact_id=kid)
        rec1 = ct.record("act-012", {"risk": 1.0})  # mismatch → 0.25

        # 验证纠错 draft 已提议
        props = kg_facts.list_proposals()
        correction = [p for p in props if p.get("corrects") == kid]
        assert len(correction) == 1
        assert correction[0]["status"] == "draft"
        assert correction[0]["subject"] == "EMP:li"
        assert correction[0]["predicate"] == "~tacit_judges"

    def test_experience_captured(self, cleared):
        """后果回流 → 经验库 outcome_records 应有记录。"""
        ct = ConsequenceTracker()
        ct.expect_outcome("act-020", "energy_carbon", {"oee": 0.85})
        ct.record("act-020", {"oee": 0.85})
        outcomes = experience.outcome_records(agent="energy_carbon")
        assert len(outcomes) >= 1
        assert outcomes[0]["decision"] == "validated"

    def test_uns_event_triggers_auto_capture(self, cleared):
        """UNS gateway 事件含 action_id → 自动触发后果捕获。"""
        import src.runtime.consequence as cmod
        # 先注册预期
        cmod.consequence.expect_outcome("act-auto-1", "energy_carbon", {"power_kw": 50.0})
        # 发布 UNS gateway 事件（模拟执行结果回流）
        uns.publish_gateway("opcua://actuator", {
            "action_id": "act-auto-1",
            "power_kw": 50.0,
        })
        # 等待钩子执行
        recs = cmod.consequence.query(agent="energy_carbon")
        # UNS 订阅是同步的（publish 内 _notify 立即执行），应该已捕获
        matched = [r for r in recs if r.get("action_id") == "act-auto-1"]
        assert len(matched) >= 1
        assert matched[0]["match"] is True

    def test_resilience_kg_down(self, cleared, monkeypatch):
        """KG 不可达时经验库仍记录（韧性降级）。"""
        def boom(*a, **k):
            raise RuntimeError("kg down")

        monkeypatch.setattr(kg_facts, "validate_fact", boom)
        fact = kg_facts.propose("default", "energy_carbon", "EMP:z", "tacit_judges", "测试", confidence=0.80)
        ct = ConsequenceTracker()
        ct.expect_outcome("act-r-1", "energy_carbon", {"v": 1}, linked_fact_id=fact["id"])
        ct.record("act-r-1", {"v": 1.0})
        # 经验库应正常记录
        outcomes = experience.outcome_records(agent="energy_carbon")
        assert len(outcomes) >= 1
