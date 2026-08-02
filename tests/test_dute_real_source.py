"""P1-4 杜特第0号真实客户·真实信号源钩子测试（北极星真实率起跳）

验证：
1. seed_dute_real 读取杜特自有真实业务上下文，标记 real_time=True
2. north_star_report 真实率从 0% 起跳（real_time_active=True，率=1.0）
3. 幂等：重复调用不重复累计
4. ZHIYAN_DUTE_REAL=0 时禁用，真实率保持 0%
"""
from __future__ import annotations

import pytest

from src.runtime.core.metrics import MetricsStore
from src.runtime.real_source import dute_real
from src.runtime.real_source.dute_real import SEED_PREFIX, seed_dute_real


@pytest.fixture
def fresh_metrics():
    from src.runtime.core import metrics as m

    saved_m = m.metrics
    saved_d = dute_real.metrics
    store = MetricsStore()
    m.metrics = store
    dute_real.metrics = store
    yield store
    m.metrics = saved_m
    dute_real.metrics = saved_d


def test_dute_real_seed_records_real_events(fresh_metrics):
    summary = seed_dute_real()
    assert summary["loaded"] is True
    assert summary["real_time"] is True
    assert summary["total"] == 12
    assert summary["realized"] == 12

    rep = fresh_metrics.north_star_report()
    assert rep["real_time_active"] is True
    assert rep["decision_realization_count_real"] == 12
    assert rep["decision_realization_rate_real"] == 1.0
    # demo 率不受影响（演示态与真实率严格分离）
    assert rep["demo_data_active"] is False


def test_dute_real_idempotent(fresh_metrics):
    seed_dute_real()
    first = fresh_metrics.north_star_report()["decision_realization_count_real"]
    # 再次调用应幂等（跨重启不重复累计）
    seed_dute_real()
    second = fresh_metrics.north_star_report()["decision_realization_count_real"]
    assert first == second == 12
    assert fresh_metrics.already_seeded(SEED_PREFIX) is True


def test_dute_real_disabled_when_flag_off(fresh_metrics, monkeypatch):
    monkeypatch.setenv("ZHIYAN_DUTE_REAL", "0")
    summary = seed_dute_real()
    assert summary["loaded"] is False
    assert summary["reason"] == "disabled"
    assert fresh_metrics.north_star_report()["real_time_active"] is False


# ============ 主动决策实时化率（2026-08-02 OpenClaw HEARTBEAT 借鉴）============


def test_north_star_includes_proactive_dimension(fresh_metrics):
    """北极星报告含主动决策维度（计数 + 率 + 来源标注，诚实 seed 演示态）。"""
    rep = fresh_metrics.north_star_report()
    assert "proactive_decision_count" in rep
    assert "proactive_decision_rate" in rep
    assert "proactive_source" in rep
    assert "heartbeat" in rep["proactive_source"]
    # 无心跳告警时：计数 0，率为 None（0 触达不虚报）
    assert rep["proactive_decision_count"] == 0
    assert rep["proactive_decision_rate"] is None


def test_proactive_rate_reflects_heartbeat_alerts(fresh_metrics, monkeypatch):
    """主动决策率 = 心跳告警 ÷ (决策事件 + 心跳告警)。"""
    from src.runtime.heartbeat.engine import heartbeat_engine

    # 注入 1 条真实决策事件（杜特信号 seed）
    from src.runtime.real_source.dute_real import seed_dute_real

    seed_dute_real()
    monkeypatch.setattr(heartbeat_engine, "_alerts", 3)  # 模拟 3 次心跳主动告警
    rep = fresh_metrics.north_star_report()
    # 3 / (12 + 3) = 0.2
    assert rep["proactive_decision_count"] == 3
    assert rep["proactive_decision_rate"] == 0.2
