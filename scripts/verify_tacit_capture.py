#!/usr/bin/env python
"""端到端验证 v21.5：隐性捕获 —— UNS 人/社交/会议/协作四路 → 经验库捕获 + 知识图谱锚定

验证「阶段 3 隐性捕获扩面」核心链路（抽取即锚定）：
  1. UNS 四路隐性信号经订阅者捕获进经验库（人/社交/会议/协作）
  2. 抽取出的结构化事实锚定到知识图谱（kg_facts draft 待审批门）
  3. gateway/system 路只上行孪生体，不触发隐性捕获
  4. 抽取启发式正确（subject/predicate/object_val）

用法（项目 .venv）：
    E:/agent_industry/zhiyan/.venv/Scripts/python.exe scripts/verify_tacit_capture.py
"""

import sys

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.uns import uns  # noqa: E402  (import 即注册隐性捕获订阅者)
from src.runtime.experience import experience  # noqa: E402
from src.runtime.evolution.kg_facts import kg_facts  # noqa: E402
from src.runtime.tacit_capture import init_tacit_capture  # noqa: E402


def main():
    # 只清事件与记录，保留订阅钩子（切勿 uns.clear()，会清掉订阅者）
    uns._events.clear()
    experience._records.clear()
    kg_facts._proposals.clear()
    init_tacit_capture()

    # ---- 1. 四路隐性信号 → 经验库捕获 ----
    uns.publish_human("wecom://zhang", {"content": "供应商A交期风险高"}, entities=["EMP:zhang", "SUP:A"])
    uns.publish_social("email://proc", {"content": "铜价本周上涨 8%"}, entities=["MAT:CU"])
    uns.publish_meeting("meet://strategy", {"summary": "Q3 预算通过，优先自动化"}, entities=["EMP:li"])
    uns.publish_collab(
        "collab://community-equipment",
        {"content": "液压机建议更换密封件"},
        entities=["DEV:hyd-105", "LINE:3"],
    )
    caps = experience.tacit_captures()
    assert len(caps) == 4, f"四路隐性捕获应=4，实际={len(caps)}"
    print("✅ [v21.5-1] UNS 人/社交/会议/协作四路隐性信号已捕获进经验库")

    # ---- 2. 抽取即锚定 → KG draft ----
    props = kg_facts.list_proposals()
    assert len(props) == 4, f"KG 待审批事实应=4，实际={len(props)}"
    assert all(p["status"] == "draft" for p in props)
    print("✅ [v21.5-2] 抽取即锚定：四路信号锚定为知识图谱 draft 事实（待审批门）")

    # ---- 3. gateway/system 路不触发隐性捕获 ----
    uns.publish_gateway("opcua://line-3", {"energy_kwh__SMT-L01": 51000.0})
    uns.publish_system("erp://sap/mm", {"doc": "PO123"})
    assert len(experience.tacit_captures()) == 4, "gateway/system 不应触发隐性捕获"
    print("✅ [v21.5-3] gateway/system 路只上行孪生体，不触发隐性捕获（职责分离）")

    # ---- 4. 抽取启发式正确性 ----
    human_fact = next(c["extracted"] for c in caps if c["channel"] == "human")
    assert human_fact["subject"] == "EMP:zhang"
    assert human_fact["predicate"] == "tacit_judges"
    assert "交期风险" in human_fact["object_val"]
    meeting_fact = next(c["extracted"] for c in caps if c["channel"] == "meeting")
    assert meeting_fact["predicate"] == "decided"
    print(f"✅ [v21.5-4] 抽取启发式正确：{human_fact['subject']} —{human_fact['predicate']}→ {human_fact['object_val']}")

    print("\n🎉 v21.5 隐性捕获端到端验证全部通过：五路感知 ③④⑤（人/社交/会议/协作）隐性信号已抽取即锚定，对手零覆盖的差异化壁垒落地")


if __name__ == "__main__":
    main()
