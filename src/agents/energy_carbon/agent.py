"""能源碳 ESG Agent——能耗监控、碳排放/碳足迹核算、ESG 合规、节能机会

企业级「经营大脑」第二部分：把制造过程的能源消耗转化为碳排放与碳强度，
识别高耗能/低绿电环节，输出节能降碳机会与 ESG 合规视图。

数据层：通过 EnergyCarbonTools 从种子数据加载（可切换真实 EMS/碳平台）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.energy_carbon.tools import EnergyCarbonTools

logger = logging.getLogger(__name__)


class EnergyCarbonAgent(BaseAgent):
    """能源碳 ESG Agent"""

    name = "energy_carbon"
    description = "能耗监控、碳排放/碳足迹核算、ESG 合规与节能降碳机会"

    def __init__(self):
        self.tools = EnergyCarbonTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「能源碳 ESG Agent」，专注制造企业的能源管理与碳管理。

## 核心能力
1. 能耗监控（各产线 kWh 统计与对标）
2. 碳排放核算（电网排放因子 × 非绿电能耗 → tCO2）
3. 碳强度计算（tCO2 / 单位产出，用于对标与趋势）
4. 绿电比例评估与提升建议
5. 节能降碳机会识别（空压机能效/绿电/余热回收等，含回收期）

## 工作原则
- 双碳合规：碳强度低于目标值为优，超出需预警
- 绿电优先：低绿电比例(<15%)环节为重点改善对象
- 数据驱动：排放因子采用区域电网公开均值，可审计可追溯
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[EnergyCarbon Agent] Analyzing: {goal[:60]}...")

        lines = await self.tools.get_energy_list()
        summary = await self.tools.get_carbon_summary()

        opportunities = []
        for op in self.tools.OPPORTUNITIES:
            opp = dict(op)
            if "saving_kwh" in op:
                opp["saving_co2_t"] = round(op["saving_kwh"] / 1000 * self.tools.GRID_FACTOR, 1)
            opportunities.append(opp)

        total_saving_kwh = sum(o.get("saving_kwh", 0) for o in opportunities)
        total_saving_co2 = round(sum(o.get("saving_co2_t", 0) for o in opportunities), 1)
        intensity_gap = round(summary["intensity_per_10k"] - summary["target_intensity"], 3) if isinstance(summary["intensity_per_10k"], (int, float)) else None

        actions_taken = []
        # 授权内行动：对低绿电(<15%)高耗能环节生成节能任务（自动）
        for ln in lines:
            if ln["green_ratio"] < 15:
                task = await self.tools.create_saving_task(f"提升{ln['name']}绿电比例")
                actions_taken.append({
                    "type": "create_saving_task",
                    "detail": f"为 {ln['name']}（绿电 {ln['green_ratio']}%）生成节能降碳任务",
                    "line_id": ln["line_id"],
                    "confidence": 0.82,
                    "status": "auto_executed",
                })

        recommendations = self._generate_recommendations(lines, summary, opportunities)

        return {
            "status": "completed",
            "summary": (
                f"能源碳分析完成：周能耗 {summary['total_energy_kwh']:,} kWh，"
                f"碳排放 {summary['total_carbon_t']} tCO2，绿电比例 {summary['green_ratio']}%；"
                f"识别节能降碳机会 {len(opportunities)} 项，潜在降碳 {total_saving_co2} tCO2"
            ),
            "total_energy_kwh": summary["total_energy_kwh"],
            "total_carbon_t": summary["total_carbon_t"],
            "green_ratio": summary["green_ratio"],
            "carbon_intensity": summary["intensity_per_10k"],
            "target_intensity": summary["target_intensity"],
            "intensity_gap": intensity_gap,
            "total_saving_kwh": total_saving_kwh,
            "total_saving_co2_t": total_saving_co2,
            "lines": lines,
            "opportunities": opportunities,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, lines, summary, opportunities) -> list:
        recs = []
        recs.append(f"🌿 当前绿电比例 {summary['green_ratio']}%，目标建议 ≥ 30%")
        low_green = [l for l in lines if l["green_ratio"] < 15]
        if low_green:
            recs.append(f"🔴 低绿电高耗能环节 {len(low_green)} 处，优先改造：")
            for l in low_green:
                recs.append(f"   → {l['name']}：绿电 {l['green_ratio']}%，周碳排 {l['carbon_t']} tCO2")
        else:
            recs.append("✅ 各产线绿电比例均在可接受范围")
        recs.append(f"💡 节能降碳机会 {len(opportunities)} 项，合计潜在降碳 {sum(o.get('saving_co2_t',0) for o in opportunities):.1f} tCO2/周：")
        for o in sorted(opportunities, key=lambda x: x.get("payback_yr", 99)):
            recs.append(f"   → {o['measure']}：回收期 {o['payback_yr']} 年，投资 {o['cost_wan']} 万")
        recs.append("📋 建议将碳强度纳入月度 ESG 披露看板，对标行业基准")
        return recs


energy_carbon_agent = EnergyCarbonAgent()
