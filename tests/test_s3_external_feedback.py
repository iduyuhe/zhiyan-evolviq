"""外部反馈响应专项测试（GitHub xingswxingsw #44/#47）。

#47：经验库遍历记录时硬编码 r["agent"]，隐性捕获记录无该键 → KeyError →
     /governance/panel 恒 500。修复后须对缺键记录容错。
#44：config 用 env_prefix="zhiyan_"，只认 ZHIYAN_* 前缀变量；无前缀变量应读不到。
"""
import pytest

from src.runtime.experience import ExperienceStore
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_experience_tolerates_records_without_agent_key():
    """模拟隐性捕获（tacit）记录无 'agent' 键，三处遍历都不能抛 KeyError。"""
    store = ExperienceStore()
    store._records.append({"decision": "approved", "created_at": _now(), "context": "tacit-no-agent"})
    store._records.append({"agent": None, "decision": "rejected", "created_at": _now(), "context": "tacit-none-agent"})
    store._records.append({"agent": "supply_chain", "decision": "approved", "created_at": _now()})

    summary = store.agent_feedback_summary("supply_chain")
    assert summary["agent"] == "supply_chain"
    assert summary["approvals"] == 1
    assert summary["rejections"] == 0

    prefs = store.get_preferences("supply_chain")
    assert [p for p in prefs if p.get("agent") == "supply_chain"]
    forb = store.get_forbidden("supply_chain")
    assert all(f.get("agent") != "supply_chain" for f in forb)


def test_experience_unknown_agent_safe_empty():
    store = ExperienceStore()
    store._records.append({"decision": "approved", "created_at": _now()})  # 无 agent
    s = store.agent_feedback_summary("does_not_exist")
    assert s["approvals"] == 0 and s["rejections"] == 0


def test_config_reads_zhiyan_prefixed_vars(monkeypatch):
    """GitHub #44：env_prefix=zhiyan_ 必须让 ZHIYAN_* 变量生效。"""
    from src.common.config import Settings

    monkeypatch.setenv("ZHIYAN_LLM_API_KEY", "sk-test-abc")
    monkeypatch.setenv("ZHIYAN_NEO4J_URI", "bolt://neo4j-x:7687")
    monkeypatch.setenv("ZHIYAN_HUNYUAN_API_KEY", "hy-test")
    s = Settings()
    assert s.llm_api_key == "sk-test-abc"
    assert s.neo4j_uri == "bolt://neo4j-x:7687"
    assert s.hunyuan_api_key == "hy-test"


def test_config_unprefixed_vars_ignored(monkeypatch):
    """GitHub #44 反面：无前缀变量（旧 .env.example 写法）应读不到，证明必须加前缀。"""
    from src.common.config import Settings

    # 清掉可能的前缀值，再设一个无前缀的
    monkeypatch.delenv("ZHIYAN_LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "should-not-bind")
    s = Settings()
    # 默认值（空）应为空，而非无前缀变量的值
    assert s.llm_api_key != "should-not-bind"
