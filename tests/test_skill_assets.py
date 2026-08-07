"""技能资产化 v0.1 + 记忆生命周期 测试。

验证：
- SKILL 信号落库为技能候选（零真名脱敏、幂等）
- 人工审批门 approve / archive
- lifecycle_gc 归档过期 proposed 草稿
- evolution_loop.apply_signals 把 SKILL 信号正确路由到 skill_asset_store

注：统一用 db_path="disabled"（SQLite 不可用 → 纯内存），既验证降级韧性，
又避免 Windows 下临时库文件锁导致的 teardown 噪声。
"""

import pytest

from src.common.leak import LEAK_TOKENS
from src.runtime.evolution_loop import (
    ASSET_SKILL,
    AssetUpdateIntent,
    EvaluationSignal,
    EvolutionLoop,
)
from src.runtime.evolution import skill_assets as sa_mod
from src.runtime.evolution.skill_assets import (
    PROPOSED_TTL_DAYS,
    SkillAsset,
    SkillAssetStore,
)

MEM = "disabled"  # 纯内存模式


def _skill_signal(text: str, sig_id: str = "ev-test-1") -> EvaluationSignal:
    return EvaluationSignal(
        signal_id=sig_id,
        source="feedback",
        signal_kind="idea",
        asset_target=ASSET_SKILL,
        agent="user",
        industry_key="semiconductor",
        payload={"feedback_type": "idea", "text": text},
    )


def test_ingest_creates_proposed_skill_zero_leak():
    store = SkillAssetStore(db_path=MEM)
    sig = _skill_signal("建议对缺料风险加权重")
    sk = store.ingest_from_signal(sig)
    assert isinstance(sk, SkillAsset)
    assert sk.status == "proposed"
    assert sk.source_signal_id == sig.signal_id
    for tok in LEAK_TOKENS:  # 零真名：描述不得含任何真实锚定 token
        assert tok not in sk.description
    assert store.get(sk.skill_id).status == "proposed"
    store.lifecycle_gc()  # 不应误删新草稿
    assert store.get(sk.skill_id) is not None


def test_ingest_idempotent_same_signal():
    store = SkillAssetStore(db_path=MEM)
    sig = _skill_signal("改进供应链推演", sig_id="ev-dup")
    sk1 = store.ingest_from_signal(sig)
    sk2 = store.ingest_from_signal(sig)
    assert sk1.skill_id == sk2.skill_id
    assert len(store.list_skills()) == 1


def test_approve_and_archive():
    store = SkillAssetStore(db_path=MEM)
    sk = store.ingest_from_signal(_skill_signal("终审改进建议 A"))
    assert store.approve(sk.skill_id, by="admin") is True
    assert store.get(sk.skill_id).status == "approved"
    assert store.archive(sk.skill_id) is False  # approved 不可再 decision
    sk2 = store.ingest_from_signal(_skill_signal("终审改进建议 B", sig_id="ev-2"))
    assert store.archive(sk2.skill_id, by="admin") is True
    assert store.get(sk2.skill_id).status == "archived"
    stats = store.stats()
    assert stats["approved"] == 1
    assert stats["total"] == 2


def test_lifecycle_gc_archives_expired_proposed():
    store = SkillAssetStore(db_path=MEM)
    sk = store.ingest_from_signal(_skill_signal("过期草稿", sig_id="ev-old"))
    sk.created_at = sk.created_at - (PROPOSED_TTL_DAYS + 5) * 86400  # 远超 TTL
    archived = store.lifecycle_gc(ttl_days=PROPOSED_TTL_DAYS)
    assert archived == 1
    assert store.get(sk.skill_id).status == "archived"


def test_evolution_loop_routes_skill_signal(monkeypatch):
    loop = EvolutionLoop(db_path=MEM)
    fresh_store = SkillAssetStore(db_path=MEM)
    monkeypatch.setattr(sa_mod, "skill_asset_store", fresh_store)

    sig = _skill_signal("从终审记录长出的技能", sig_id="ev-loop-1")
    loop._signals.append(sig)
    added = loop.apply_signals()
    assert added >= 1
    skills = fresh_store.list_skills()
    assert len(skills) == 1
    assert skills[0].source_signal_id == "ev-loop-1"
    skill_intents = loop.intents(channel=ASSET_SKILL)
    assert len(skill_intents) == 1


def test_lifecycle_gc_on_loop_archives_stale_intents(monkeypatch):
    loop = EvolutionLoop(db_path=MEM)
    monkeypatch_store = SkillAssetStore(db_path=MEM)
    monkeypatch.setattr(sa_mod, "skill_asset_store", monkeypatch_store)

    old = AssetUpdateIntent(
        intent_id="au-old", channel=ASSET_SKILL, signal_id="ev-x",
        agent="user", proposed_change="旧草稿", created_at=0,  # 远早于 TTL
    )
    loop._intents.append(old)
    res = loop.lifecycle_gc(ttl_days=30)
    assert res["intents_archived"] == 1
    assert loop.intents()[0].status == "expired"
