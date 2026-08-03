"""刀4·迭代1 测试：评估信号采集（挖存量：consequence + feedback_store）。

覆盖：
- collect：从执行后果派生 validated/contradicted 信号；从人工反馈派生 like/dislike/idea 信号。
- 零真名：含 LEAK_TOKENS 的反馈信号被丢弃（不进评估信号库）。
- 去重：同一 linked_id 仅采集一次。
- 归一：ExecutionSignal 路由到正确 asset_target（validated→threshold, contradicted→skill, 关联事实→kg）。
- 统计 / 持久化（SQLite 韧性降级纯内存）。
"""
from src.agents.compliance_reviewer.agent import LEAK_TOKENS
from src.runtime.evolution_loop import EvolutionLoop, _derive_execution_signal


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


def _consequence_rec(cid, match, linked_fact_id=None):
    return {
        "id": cid,
        "agent": "supply_chain",
        "match": match,
        "match_detail": {"matched_keys": 2, "total_keys": 2},
        "linked_fact_id": linked_fact_id,
    }


def _feedback(fid, ftype, text, tid=""):
    return {
        "id": fid,
        "feedback_type": ftype,
        "text": text,
        "desensitized_text": text,
        "target_kind": "agent",
        "target_id": tid,
    }


def test_collect_execution_validated_routes_threshold():
    rec = _consequence_rec("cr-1", match=True)
    loop = EvolutionLoop(db_path="disabled")
    n = loop.collect(consequence_tracker=_FakeTracker([rec]), feedback_store=_FakeFbStore([]))
    assert n == 1
    sig = loop.signals(asset_target="threshold")[0]
    assert sig.signal_kind == "validated"
    assert sig.agent == "supply_chain"


def test_collect_execution_contradicted_routes_skill():
    rec = _consequence_rec("cr-2", match=False)
    loop = EvolutionLoop(db_path="disabled")
    loop.collect(consequence_tracker=_FakeTracker([rec]), feedback_store=_FakeFbStore([]))
    sig = loop.signals(asset_target="skill")[0]
    assert sig.signal_kind == "contradicted"


def test_collect_execution_with_fact_routes_kg_on_mismatch():
    rec = _consequence_rec("cr-3", match=False, linked_fact_id="kf-9")
    sig = _derive_execution_signal(rec)
    assert sig.asset_target == "kg"
    assert sig.payload.get("linked_fact_id") == "kf-9"


def test_collect_feedback_like_dislike_idea():
    fbs = [
        _feedback("fb-1", "like", "很有用"),
        _feedback("fb-2", "dislike", "不准"),
        _feedback("fb-3", "idea", "建议加报表", tid="case_x"),
    ]
    loop = EvolutionLoop(db_path="disabled")
    n = loop.collect(consequence_tracker=_FakeTracker([]), feedback_store=_FakeFbStore(fbs))
    assert n == 3
    kinds = {s.signal_kind for s in loop.signals()}
    assert {"like", "dislike", "idea"} <= kinds
    # idea 信号应带 case_id（零真名，仅 case 维度）
    idea = [s for s in loop.signals() if s.signal_kind == "idea"][0]
    assert idea.case_id == "case_x"


def test_collect_feedback_leak_token_discarded():
    """含真实锚定名的反馈信号必须被丢弃（零真名铁律）。"""
    leak = _feedback("fb-leak", "idea", f"关于{LEAK_TOKENS[0]}的建议")
    loop = EvolutionLoop(db_path="disabled")
    n = loop.collect(consequence_tracker=_FakeTracker([]), feedback_store=_FakeFbStore([leak]))
    assert n == 0, "含真名反馈不应进入评估信号库"
    assert loop.stats()["total"] == 0


def test_collect_deduplicates_by_linked_id():
    rec = _consequence_rec("cr-dup", match=True)
    loop = EvolutionLoop(db_path="disabled")
    n1 = loop.collect(consequence_tracker=_FakeTracker([rec]), feedback_store=_FakeFbStore([]))
    n2 = loop.collect(consequence_tracker=_FakeTracker([rec]), feedback_store=_FakeFbStore([]))
    assert n1 == 1 and n2 == 0
    assert loop.stats()["total"] == 1


def test_stats_breakdown():
    recs = [_consequence_rec("cr-4", True), _consequence_rec("cr-5", False)]
    fbs = [_feedback("fb-4", "like", "好"), _feedback("fb-5", "idea", "加功能")]
    loop = EvolutionLoop(db_path="disabled")
    loop.collect(consequence_tracker=_FakeTracker(recs), feedback_store=_FakeFbStore(fbs))
    st = loop.stats()
    assert st["total"] == 4
    assert st["by_source"]["execution"] == 2
    assert st["by_source"]["feedback"] == 2
    # validated→threshold(1)；contradicted→skill(1)；idea→skill(1) ⇒ skill=2
    assert st["by_asset_target"].get("threshold") == 1
    assert st["by_asset_target"].get("skill") == 2
    assert st["by_asset_target"].get("memory") == 1


def test_serialized_signals_contain_no_real_name():
    """所有评估信号序列化后均不得含真实锚定 token（零真名铁律）。"""
    recs = [_consequence_rec("cr-6", True), _consequence_rec("cr-7", False)]
    fbs = [_feedback("fb-6", "like", "好用"), _feedback("fb-7", "idea", "加报表")]
    loop = EvolutionLoop(db_path="disabled")
    loop.collect(consequence_tracker=_FakeTracker(recs), feedback_store=_FakeFbStore(fbs))
    import json
    blob = json.dumps([s.to_dict() for s in loop.signals()], ensure_ascii=False)
    hits = [t for t in LEAK_TOKENS if t in blob]
    assert not hits, f"❌ 评估信号泄露真实锚定名：{hits}"
