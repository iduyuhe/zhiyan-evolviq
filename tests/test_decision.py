"""刀3 决策引擎 + 决策事件 · 迭代1 测试（DecisionProposal 结构 + 持久化 + 证据链零真名）

覆盖：
- build_proposal：标准结构（候选动作 + 多目标权衡 + 约束校验 + 证据链）；约束不通过时
  recommended_action 置空（治理前置）。
- DecisionStore：save/get 往返、list_by_industry、mark_decided / mark_executed 状态流转。
- 证据链只引用 case_id（零真名）；提案/事件序列化不含 LEAK_TOKENS 真实锚定片段。

范围纪律（docs/TECHNICAL_DELIVERY_SCOPE.md）：纯后端，SQLite 复用（韧性降级纯内存），
不扩 agent / 前端 / REST 端点，符合延迟部署纪律。
"""
import json

import pytest

from src.agents.compliance_reviewer.agent import LEAK_TOKENS
from src.runtime.decision import (
    DecisionStore, DecisionProposal, build_proposal,
    CandidateAction, ConstraintCheck, EvidenceLink,
)


def _make_proposal(recommend: str = "lock_alt", fail_constraint: bool = False,
                   industry_key: str = "semiconductor") -> DecisionProposal:
    return build_proposal(
        title="半导体代工产能短缺对策",
        context={"industry_key": industry_key, "node_category": "代工",
                  "scope": "domestic"},
        candidate_actions=[
            CandidateAction("lock_alt", "锁定替代料保产", 0.8),
            CandidateAction("expedite", "加速加急订单", 0.6),
        ],
        tradeoffs={
            "成本": {"lock_alt": 0.7, "expedite": 0.4},
            "交期": {"lock_alt": 0.8, "expedite": 0.9},
            "风险": {"lock_alt": 0.9, "expedite": 0.5},
        },
        constraints=[
            ConstraintCheck("库存可用", passed=not fail_constraint,
                            reason="替代料库存充足" if not fail_constraint else "库存不足"),
        ],
        evidence=[
            EvidenceLink("case", "case_semicon_2026", "代工产能瓶颈公开披露"),
            EvidenceLink("kg_node", "industry_node:semiconductor:代工", "节点对标"),
        ],
        recommended_action=recommend,
    )


def test_build_proposal_recommends_when_constraints_pass():
    p = _make_proposal()
    assert p.recommended_action == "lock_alt"
    assert p.status == "proposed"


def test_build_proposal_suppresses_when_constraint_fails():
    p = _make_proposal(fail_constraint=True)
    assert p.recommended_action is None, "约束不通过应抑制推荐（治理前置）"
    assert p.constraints[0].passed is False


def test_store_save_get_roundtrip(tmp_path):
    store = DecisionStore(db_path=str(tmp_path / "decision.db"))
    p = _make_proposal()
    store.save(p)
    got = store.get(p.proposal_id)
    assert got is not None
    assert got.title == p.title
    assert got.recommended_action == "lock_alt"
    assert len(got.evidence) == 2
    assert got.evidence[0].ref == "case_semicon_2026"


def test_store_list_by_industry(tmp_path):
    store = DecisionStore(db_path=str(tmp_path / "decision.db"))
    store.save(_make_proposal(industry_key="semiconductor"))
    store.save(_make_proposal(industry_key="semiconductor"))
    store.save(_make_proposal(industry_key="telecom"))
    semi = store.list_by_industry("semiconductor")
    assert len(semi) == 2
    assert all(p.context.get("industry_key") == "semiconductor" for p in semi)


def test_store_decide_and_execute(tmp_path):
    store = DecisionStore(db_path=str(tmp_path / "decision.db"))
    p = _make_proposal()
    store.save(p)
    d = store.mark_decided(p.proposal_id, "lock_alt", actor="human")
    assert d.status == "decided" and d.decided_action == "lock_alt"
    e = store.mark_executed(p.proposal_id)
    assert e.status == "executed"
    # 持久化后读回状态一致
    assert store.get(p.proposal_id).status == "executed"


def test_store_stats(tmp_path):
    store = DecisionStore(db_path=str(tmp_path / "decision.db"))
    store.save(_make_proposal())
    store.save(_make_proposal())
    s = store.mark_decided(store.list_by_industry("semiconductor")[0].proposal_id, "lock_alt")
    stats = store.stats()
    assert stats.get("proposed", 0) + stats.get("decided", 0) >= 2


def test_north_star_real_time_rate(tmp_path):
    """刀3 迭代2：北极星 决策实时化率 埋点。

    语义：已执行 / 提案总数；随闭环执行比例上升。
    """
    store = DecisionStore(db_path=str(tmp_path / "decision.db"))
    # 空库 -> 0.0（避免除零）
    assert store.north_star()["real_time_rate"] == 0.0

    p1 = _make_proposal()
    p2 = _make_proposal()
    p3 = _make_proposal()
    store.save(p1)
    store.save(p2)
    store.save(p3)
    # 0/3 执行 -> 0.0
    assert store.north_star()["real_time_rate"] == 0.0

    store.mark_executed(p1.proposal_id)
    # 1/3 执行 -> 0.333...
    snap = store.north_star()
    assert snap["total"] == 3 and snap["executed"] == 1
    assert abs(snap["real_time_rate"] - 1 / 3) < 1e-6

    store.mark_executed(p2.proposal_id)
    # 2/3 -> 0.666...
    assert abs(store.north_star()["real_time_rate"] - 2 / 3) < 1e-6

    store.mark_executed(p3.proposal_id)
    # 3/3 -> 1.0（稳态目标之上）
    assert store.north_star()["real_time_rate"] == 1.0
    assert store.north_star()["target_steady"] == 0.85


def test_evidence_zero_real_name():
    """证据链只引用 case_id / kg_node，提案序列化不得含真实锚定名。"""
    p = _make_proposal()
    blob = json.dumps(p.to_dict(), ensure_ascii=False)
    hits = [t for t in LEAK_TOKENS if t in blob]
    assert not hits, f"❌ 决策提案泄露真实锚定名：{hits}"
    # 证据 ref 均不含真名（仅 case_id / 节点 id）
    for ev in p.evidence:
        assert ev.ref.startswith(("case_", "industry_node:")), ev.ref
