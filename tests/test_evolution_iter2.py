"""刀4·迭代2 测试：资产更新通道 + L0→L3 进化阶梯（挖存量：experience / strategy_tuner）。

覆盖：
- apply_signals：信号路由到四类资产通道（记忆/图谱/技能/阈值），产出 proposed 意图。
- 铁律：自进化绝不自动应用 —— 所有意图 status=proposed，无 applied。
- 幂等：同 signal_id 只产出一次意图。
- 真实记忆通道：默认 memory updater 调 experience.record_feedback（验证接线）。
- L0→L3 阶梯可观测：L1 已采集 / L2 已产出意图 / L3 跨 ≥2 agent 复利。
- 零真名：意图序列化无 LEAK_TOKENS。
"""
import json

from src.agents.compliance_reviewer.agent import LEAK_TOKENS
from src.runtime.evolution_loop import (
    EvolutionLoop,
    ASSET_MEMORY, ASSET_KG, ASSET_SKILL, ASSET_THRESHOLD,
    L0_STATIC_SEED, L1_RUNTIME_COLLECTED, L2_EVAL_DRIVEN, L3_CROSS_ENTERPRISE,
)


class _FakeTracker:
    def __init__(self, recs):
        self._recs = recs

    def query(self, agent=None, limit=100):
        return self._recs[:limit]


class _FakeFbStore:
    def __init__(self, fbs):
        self._fbs = fbs

    def list_all(self):
        return self._fbs


def _consequence_rec(cid, match, agent="supply_chain"):
    return {
        "id": cid, "agent": agent, "match": match,
        "match_detail": {"matched_keys": 1, "total_keys": 1}, "linked_fact_id": None,

    }


def _feedback(fid, ftype, text, tid=""):
    return {"id": fid, "feedback_type": ftype, "text": text,
            "desensitized_text": text, "target_kind": "agent", "target_id": tid}


def _collect_all(loop):
    recs = [
        _consequence_rec("cr-a", True, "supply_chain"),
        _consequence_rec("cr-b", False, "cost_analysis"),
    ]
    fbs = [
        _feedback("fb-a", "like", "有用", tid="case_x"),
        _feedback("fb-b", "dislike", "不准", tid="case_y"),
        _feedback("fb-c", "idea", "加报表", tid="case_z"),
    ]
    return loop.collect(consequence_tracker=_FakeTracker(recs), feedback_store=_FakeFbStore(fbs))


def test_apply_routes_and_proposes():
    loop = EvolutionLoop(db_path="disabled")
    _collect_all(loop)
    calls = []

    def _fake(sig):
        calls.append((sig.asset_target, sig.signal_id))

    n = loop.apply_signals(updaters={
        ASSET_MEMORY: _fake, ASSET_KG: _fake, ASSET_SKILL: _fake, ASSET_THRESHOLD: _fake,
    })
    assert n == 5, f"应路由 5 条信号，实际 {n}"
    assert len(calls) == 5
    # 每条信号至少产一条 proposed 意图
    intents = loop.intents()
    assert len(intents) == 5
    assert all(i.status == "proposed" for i in intents), "铁律：意图必须全为 proposed，不得自动应用"


def test_no_auto_apply_iron_law():
    loop = EvolutionLoop(db_path="disabled")
    _collect_all(loop)
    loop.apply_signals(updaters={
        ASSET_MEMORY: lambda s: None, ASSET_KG: lambda s: None,
        ASSET_SKILL: lambda s: None, ASSET_THRESHOLD: lambda s: None,
    })
    for i in loop.intents():
        assert i.status == "proposed"
        assert "applied" not in i.status


def test_apply_idempotent():
    loop = EvolutionLoop(db_path="disabled")
    _collect_all(loop)
    n1 = loop.apply_signals(updaters={
        ASSET_MEMORY: lambda s: None, ASSET_KG: lambda s: None,
        ASSET_SKILL: lambda s: None, ASSET_THRESHOLD: lambda s: None,
    })
    n2 = loop.apply_signals(updaters={
        ASSET_MEMORY: lambda s: None, ASSET_KG: lambda s: None,
        ASSET_SKILL: lambda s: None, ASSET_THRESHOLD: lambda s: None,
    })
    assert n1 == 5 and n2 == 0, f"二次 apply 应幂等无新增，n1={n1} n2={n2}"
    assert len(loop.intents()) == 5


def test_ladder_levels():
    loop = EvolutionLoop(db_path="disabled")
    _collect_all(loop)
    # 仅采集：记忆/图谱/技能/阈值 全有信号 → L1
    lad = loop.evolution_ladder()
    assert lad[ASSET_MEMORY]["level"] == L1_RUNTIME_COLLECTED
    # apply 后 → L2
    loop.apply_signals(updaters={
        ASSET_MEMORY: lambda s: None, ASSET_KG: lambda s: None,
        ASSET_SKILL: lambda s: None, ASSET_THRESHOLD: lambda s: None,
    })
    lad = loop.evolution_ladder()
    assert lad[ASSET_MEMORY]["level"] == L2_EVAL_DRIVEN
    assert lad[ASSET_MEMORY]["intents_proposed"] == 1


def test_ladder_L3_cross_enterprise():
    """阈值通道意图来自 ≥2 个不同 agent → L3 跨企业/agent 复利。

    路由规则：执行匹配(match=True)→阈值；反馈 dislike→阈值（agent=user）。
    二者分属不同 agent，故阈值通道 distinct_agents≥2 → L3。
    """
    loop = EvolutionLoop(db_path="disabled")
    recs = [_consequence_rec("cr-x", True, "supply_chain")]  # match=True → 阈值
    fbs = [_feedback("fb-d", "dislike", "不准", tid="case_q")]  # dislike → 阈值，agent=user
    loop.collect(consequence_tracker=_FakeTracker(recs), feedback_store=_FakeFbStore(fbs))
    loop.apply_signals(updaters={
        ASSET_MEMORY: lambda s: None, ASSET_KG: lambda s: None,
        ASSET_SKILL: lambda s: None, ASSET_THRESHOLD: lambda s: None,
    })
    lad = loop.evolution_ladder()
    assert lad[ASSET_THRESHOLD]["distinct_agents"] >= 2
    assert lad[ASSET_THRESHOLD]["level"] == L3_CROSS_ENTERPRISE


def test_intents_zero_real_name():
    loop = EvolutionLoop(db_path="disabled")
    _collect_all(loop)
    loop.apply_signals(updaters={
        ASSET_MEMORY: lambda s: None, ASSET_KG: lambda s: None,
        ASSET_SKILL: lambda s: None, ASSET_THRESHOLD: lambda s: None,
    })
    blob = json.dumps([i.to_dict() for i in loop.intents()], ensure_ascii=False)
    hits = [t for t in LEAK_TOKENS if t in blob]
    assert not hits, f"❌ 资产更新意图泄露真实锚定名：{hits}"


def test_real_memory_updater_wires_experience(monkeypatch):
    """默认 memory updater 应真实调用 experience.record_feedback（记忆资产回灌）。"""
    import src.runtime.experience as exp_mod
    captured = {}

    def _fake_record(tenant, agent, action_type, decision, context="", note="", source="intervention"):
        captured["called"] = True
        captured["decision"] = decision
        return {"ok": True}

    monkeypatch.setattr(exp_mod.experience, "record_feedback", _fake_record)
    loop = EvolutionLoop(db_path="disabled")
    loop.collect(consequence_tracker=_FakeTracker([]),
                 feedback_store=_FakeFbStore([_feedback("fb-m", "like", "很好", tid="case_m")]))
    loop.apply_signals()  # 用默认 updaters（含真实 memory 接线）
    assert captured.get("called") is True, "默认 memory updater 应调用 experience.record_feedback"
    assert captured.get("decision") == "approved"
