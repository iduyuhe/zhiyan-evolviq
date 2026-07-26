"""v21.5 隐性捕获单元测试

验证：
1. UNS 人/社交/会议/协作四路事件 → 经验库隐性捕获 + 知识图谱 draft 锚定（抽取即锚定）
2. gateway/system 路不触发隐性捕获（只做孪生体状态上行）
3. 确定性抽取启发式（subject/predicate/object_val）
4. 韧性降级：KG 锚定失败时经验库仍捕获
5. 订阅钩子幂等注册（重复 init 不重复捕获）
"""

import pytest

from src.runtime.uns import (
    uns,
    CHANNEL_HUMAN,
    CHANNEL_SOCIAL,
    CHANNEL_MEETING,
    CHANNEL_COLLAB,
    CHANNEL_GATEWAY,
)
from src.runtime.experience import experience
from src.runtime.evolution.kg_facts import kg_facts
from src.runtime.tacit_capture import init_tacit_capture, extract_tacit_fact


@pytest.fixture
def cleared():
    # 只清事件与记录，保留 UNS 订阅者（钩子 import 即注册，不可清）
    uns._events.clear()
    experience._records.clear()
    kg_facts._proposals.clear()
    yield
    uns._events.clear()
    experience._records.clear()
    kg_facts._proposals.clear()


def test_human_capture_anchors(cleared):
    uns.publish_human(
        "wecom://zhang", {"content": "供应商A交期风险高"}, entities=["EMP:zhang", "SUP:A"]
    )
    caps = experience.tacit_captures(channel=CHANNEL_HUMAN)
    assert len(caps) == 1
    assert caps[0]["channel"] == CHANNEL_HUMAN
    assert caps[0]["extracted"]["subject"] == "EMP:zhang"
    assert caps[0]["extracted"]["predicate"] == "tacit_judges"
    # 锚定到 KG 为 draft 待审批
    props = kg_facts.list_proposals()
    assert len(props) == 1
    assert props[0]["status"] == "draft"
    assert props[0]["subject"] == "EMP:zhang"


def test_all_four_channels_captured(cleared):
    uns.publish_human("w", {"content": "h"})
    uns.publish_social("s", {"content": "s"})
    uns.publish_meeting("m", {"content": "m"})
    uns.publish_collab("c", {"content": "c"}, entities=["DEV:x"])
    assert len(experience.tacit_captures()) == 4
    # gateway/system 不应触发隐性捕获
    uns.publish_gateway("opcua://l", {"energy_kwh__L": 1.0})
    assert len(experience.tacit_captures()) == 4


def test_extract_heuristic(cleared):
    ev = uns.publish_human("w", {"judgment": "交期风险"}, entities=["EMP:z", "SUP:A"])
    fact = extract_tacit_fact(ev)
    assert fact["subject"] == "EMP:z"
    assert fact["predicate"] == "tacit_judges"
    assert "交期风险" in fact["object_val"]
    # meeting 路 → decided 谓词
    ev2 = uns.publish_meeting("m", {"summary": "Q3 预算通过"}, entities=["EMP:li"])
    fact2 = extract_tacit_fact(ev2)
    assert fact2["predicate"] == "decided"
    assert "Q3 预算通过" in fact2["object_val"]


def test_resilience_kg_sink_fails(cleared, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kg down")

    monkeypatch.setattr(kg_facts, "propose", boom)
    uns.publish_human("w", {"content": "x"})
    # KG 失败不影响经验库捕获（韧性降级，不破管）
    assert len(experience.tacit_captures()) == 1


def test_idempotent_hooks():
    before = len(uns._subscribers.get(CHANNEL_HUMAN, []))
    init_tacit_capture()
    after = len(uns._subscribers.get(CHANNEL_HUMAN, []))
    assert after == before, "重复 init 不应重复注册订阅者"
