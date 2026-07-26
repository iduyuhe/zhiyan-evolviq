#!/usr/bin/env python
"""端到端验证 T5：UNS 五路归一 → 网关流路由孪生体 → energy_carbon agent 实时结论

验证「阶段1下半场 · 第二部分（轻量 UNS 统一事件总线）」核心链路：
  1. 五路事件同 schema 归一入 UNS，各 channel 可查可回溯
  2. 网关流（gateway 路）经 UNS 自动路由到孪生体 → agent 出含 real_time_* 结论
  3. 韧性：孪生清空后 UNS 照常工作，agent 回退种子不崩

用法（项目 .venv）：
    E:/agent_industry/zhiyan/.venv/Scripts/python.exe scripts/verify_uns.py
"""

import asyncio
import sys

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.data_sources import registry as ds_registry  # noqa: E402
from src.runtime.data_sources.connectors.energy_twin import EnergyTwinDataSource  # noqa: E402
from src.runtime.uns import uns  # noqa: E402
from src.agents.energy_carbon.agent import energy_carbon_agent  # noqa: E402


def _register_energy_twin():
    ds_registry.register(EnergyTwinDataSource(tenant_id="default"))


async def main():
    _register_energy_twin()

    # ---- 1. 五路归一 ----
    uns.clear()
    uns.publish_gateway("opcua://line-3", {"energy_kwh__SMT-L01": 51000.0, "green_ratio__SMT-L01": 33.0})
    uns.publish_system("erp://sap/mm", {"doc": "PO123"})
    uns.publish_human("wecom://zhang", {"note": "供应商交期风险"})
    uns.publish_social("email://proc", {"thread": "price"})
    uns.publish_meeting("meet://strategy", {"topic": "Q3"})
    uns.publish_collab("collab://community-equipment", {"msg": "液压机建议维护"}, entities=["DEV:hyd-105"])
    counts = uns.channel_counts()
    assert all(counts.get(c, 0) == 1 for c in ["gateway", "system", "human", "social", "meeting", "collab"]), counts
    print("✅ [T5-1] 五路事件同 schema 归一入 UNS，各 channel 可查可回溯")

    # ---- 2. 网关流经 UNS 路由孪生体 → agent 实时结论 ----
    r = await energy_carbon_agent.analyze("分析本周能耗与碳排")
    tc = r["twin_context"]
    assert tc["enabled"] is True, "网关流应驱动孪生体 enabled=True"
    assert "energy_kwh" in tc["real_time_fields"], "应含 energy_kwh 实时字段"
    print(f"✅ [T5-2] 网关流经 UNS 路由孪生体 → agent 实时结论（来源 {tc['source']}）")

    # ---- 3. 韧性：清空孪生 → agent 回退种子（UNS 照常工作由 test_uns 覆盖）----
    ds_registry.clear()
    _register_energy_twin()
    r2 = await energy_carbon_agent.analyze("分析本周能耗与碳排")
    assert r2["twin_context"]["enabled"] is False, "清空后应回退种子"
    print("✅ [T5-3] 韧性：孪生清空后 agent 回退种子不崩")

    print("\n🎉 T5 UNS 五路归一端到端验证全部通过：网关实时流已先归一进 UNS 再驱动 agent 实时孪生推理")


if __name__ == "__main__":
    asyncio.run(main())
