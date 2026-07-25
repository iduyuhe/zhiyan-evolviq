"""P1 规则自学习闭环测试——经验记忆 + 带护栏自动调参 + 一键回滚

覆盖：
1. 经验库 record/recall（偏好/禁忌）
2. auto_tune 自动应用 + 冷却期护栏 + 单次上限
3. 关闭开关时不自动
4. 一键回滚还原
5. 人类反馈反哺 suggest（近期驳回 → 规则2 收紧）
6. 介入中心审批/驳回 接线经验库（端到端）
"""

import asyncio

import pytest
from httpx import AsyncClient, ASGITransport

from src.runtime.core.authorization import authorization
from src.runtime.core.intervention import Intervention, intervention_queue
from src.runtime.core.metrics import metrics
from src.runtime.core.strategy_tuner import tuner
from src.runtime.experience import experience
from src.runtime.main import app
from src.runtime.models.authorization import PlannedAction


@pytest.fixture(autouse=True)
def _reset():
    """每个测试前清空单例状态，并快照授权边界以便 teardown 还原。"""
    metrics._records = []
    experience._records = []
    intervention_queue._items = {}
    tuner._history = []
    tuner._cache = []
    tuner._last_auto_ts = {}
    tuner._auto_snapshots = []
    tuner.auto_tune_enabled = True
    snap = {}
    for b in authorization.list():
        snap[b.agent] = (b.confidence_threshold, b.max_daily_autonomous, b.id)
    yield
    for agent, (ct, mda, bid) in snap.items():
        try:
            authorization.for_tenant("default").patch(
                bid, confidence_threshold=ct, max_daily_autonomous=mda
            )
        except Exception:
            pass


def _make_intervention(agent: str, action_type: str = "lock_material") -> Intervention:
    action = PlannedAction(type=action_type, detail="test")
    return Intervention(
        session_id="s-test", agent=agent, action=action,
        reason="测试理由", boundary_id="ab-test",
    )


def _seed_widen(agent: str):
    """注入样本：自主率低 + 高批准率 → 触发规则1（放宽置信阈值）。"""
    metrics.record("s1", agent, total=10, auto=2, human=8, tenant="default")
    for _ in range(5):
        ivt = _make_intervention(agent)
        intervention_queue.push(ivt)
        intervention_queue.decide(ivt.id, True)


def test_experience_record_and_recall():
    experience._records = []
    experience.record_feedback("default", "supply_chain", "lock_material", "rejected", context="c1")
    experience.record_feedback("default", "supply_chain", "lock_material", "approved", context="c2")
    s = experience.agent_feedback_summary("supply_chain")
    assert s["approvals"] == 1 and s["rejections"] == 1 and s["recent_rejections"] == 1
    assert len(experience.get_preferences("supply_chain")) == 1
    assert len(experience.get_forbidden("supply_chain")) == 1


def test_auto_tune_applies_and_cooldown():
    _seed_widen("supply_chain")
    res = tuner.auto_tune("default")
    assert res["status"] == "applied"
    assert len(res["adjustments"]) == 1
    adj = res["adjustments"][0]
    assert adj["agent"] == "supply_chain"
    assert adj["direction"] == "widen"
    assert adj["new"] < adj["old"]  # 置信阈值下调（放权）

    # 冷却期：第二次调用应跳过该 agent
    res2 = tuner.auto_tune("default")
    assert res2["status"] == "no_change"
    assert len(res2["adjustments"]) == 0

    # 一键回滚
    rb = tuner.rollback_last_auto("default")
    assert rb["status"] == "rolled_back"
    assert len(rb["rolled_back"]) == 1
    assert rb["rolled_back"][0]["restored_to"] == adj["old"]


def test_auto_tune_disabled():
    tuner.auto_tune_enabled = False
    res = tuner.auto_tune("default")
    assert res["status"] == "disabled"
    assert res["adjustments"] == []


def test_auto_tune_max_per_run():
    for a in ["supply_chain", "dfm_check", "bom_selector", "oee_optimizer", "smt_changeover"]:
        _seed_widen(a)
    res = tuner.auto_tune("default")
    assert len(res["adjustments"]) == 3  # MAX_AUTO_PER_RUN=3


def test_feedback_feeds_suggest():
    # 自主率高、无介入队列（规则1/3 不触发），但经验库近期有驳回 → 规则2 收紧
    metrics.record("s1", "supply_chain", total=10, auto=9, human=1, tenant="default")
    experience.record_feedback("default", "supply_chain", "lock_material", "rejected", context="x")
    sugs = tuner.suggest("default")["suggestions"]
    assert any(
        s["agent"] == "supply_chain" and s["direction"] == "tighten" for s in sugs
    )


def test_decide_intervention_records_feedback():
    ivt = _make_intervention("supply_chain")
    intervention_queue.push(ivt)

    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(
                f"/interventions/{ivt.id}/decide",
                json={"approved": False, "note": "不安全"},
            )

    r = asyncio.run(_run())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    # 经验库应记录该驳回（偏好/禁忌沉淀）
    s = experience.agent_feedback_summary("supply_chain")
    assert s["rejections"] >= 1
    assert any(
        rec["decision"] == "rejected" and rec["agent"] == "supply_chain"
        for rec in experience._records
    )
