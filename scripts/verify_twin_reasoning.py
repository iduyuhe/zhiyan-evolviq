#!/usr/bin/env python
"""端到端验证：网关实时流 → 孪生体 → energy_carbon agent 实时孪生推理

验证「阶段1下半场」核心链路：
  1. 无孪生流时 → 回退种子基线（enabled=False，不崩）
  2. 模拟 OPC-UA 实时流 → route_event 汇入 energy_twin → analyze() 产出含 real_time_* 结论
  3. 韧性：清空孪生 → 再次回退种子（enabled=False，不崩）

用法（项目 .venv）：
    E:/agent_industry/zhiyan/.venv/Scripts/python.exe scripts/verify_twin_reasoning.py
"""

import asyncio
import sys

# 项目根加入 path（e2e 脚本不依赖 lifespan）
PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.data_sources import registry as ds_registry  # noqa: E402
from src.runtime.data_sources.base import HolonKind  # noqa: E402
from src.runtime.data_sources.connectors.energy_twin import EnergyTwinDataSource  # noqa: E402
from src.agents.energy_carbon.agent import energy_carbon_agent  # noqa: E402


def _register_energy_twin():
    # 幂等：若 config 已注册则覆盖，不影响链路
    ds_registry.register(EnergyTwinDataSource(tenant_id="default"))


async def main():
    _register_energy_twin()

    # ---- 1. 无孪生流：回退种子基线 ----
    r0 = await energy_carbon_agent.analyze("分析本周能耗与碳排")
    assert r0["status"] == "completed", "analyze 应返回 completed"
    assert r0["twin_context"]["enabled"] is False, "无孪生流应 enabled=False"
    assert "无实时孪生流" in r0["summary"], "结论应标注使用种子基线"
    print("✅ [1] 无孪生流 → 回退种子基线，agent 不崩")

    # ---- 2. 模拟 OPC-UA 实时流 → 孪生体 → 实时结论 ----
    ds_registry.route_event(
        "machine",
        {
            "energy_kwh__SMT-L01": 51000.0,
            "power_kw__SMT-L01": 320.5,
            "green_ratio__SMT-L01": 33.0,
            "energy_kwh__DIFF": 58000.0,
            "green_ratio__DIFF": 12.0,
        },
        source="opcua-sim",
    )
    r1 = await energy_carbon_agent.analyze("分析本周能耗与碳排")
    tc = r1["twin_context"]
    assert tc["enabled"] is True, "有孪生流应 enabled=True"
    assert "energy_kwh" in tc["real_time_fields"], "应含 energy_kwh 实时字段"
    assert tc["lines"]["SMT-L01"]["energy_kwh"] == 51000.0, "SMT-L01 实时能耗应被融合"
    assert tc["fresh"] is True, "刚上行应 fresh=True"
    # 实时值覆盖种子：SMT-L01 绿电比从 30→33
    smt = next(l for l in r1["lines"] if l["line_id"] == "SMT-L01")
    assert smt["real_time"] is True and smt["green_ratio"] == 33.0, "SMT-L01 应标记为实时且绿电比=33"
    print(f"✅ [2] 实时孪生驱动 → 含 real_time_* 字段（来源 {tc['source']}），SMT-L01 能耗={smt['energy_kwh']}kWh")

    # ---- 3. 韧性：清空孪生 → 再次回退种子 ----
    ds_registry.clear()
    _register_energy_twin()  # 仅重建空孪生体
    r2 = await energy_carbon_agent.analyze("分析本周能耗与碳排")
    assert r2["twin_context"]["enabled"] is False, "清空后应回退种子"
    print("✅ [3] 孪生清空 → 韧性回退种子，agent 不崩")

    print("\n🎉 端到端验证全部通过：网关实时流已驱动 agent 产出实时孪生结论（阶段1下半场打通）")


if __name__ == "__main__":
    asyncio.run(main())
