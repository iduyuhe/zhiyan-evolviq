"""制造成本 Agent——单位成本拆解、降本机会、报价支撑

企业级「经营大脑」第三部分：把制造全过程的成本（材料/人工/设备/能源/良率损失）
结构化拆解，识别降本空间并支撑报价决策。

数据层：通过 CostAnalysisTools 从种子数据加载（可切换真实 ERP/成本系统）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.cost_analysis.tools import CostAnalysisTools

logger = logging.getLogger(__name__)


class CostAgent(BaseAgent):
    """制造成本 Agent"""

    name = "cost_analysis"
    description = "制造成本核算、单位成本拆解、降本机会与报价支撑"

    def __init__(self):
        self.tools = CostAnalysisTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「制造成本 Agent」，专注制造企业的成本核算与降本。

## 核心能力
1. 单位制造成本拆解（材料 BOM / 人工 / 设备摊销 / 能源 / 良率损失 scrap）
2. 目标成本差异(variance)与毛利率核算
3. 降本机会识别（国产替代/良率/能耗/换线提速），含单件节省
4. 报价支撑（基于成本结构给出底线价与建议价区间）

## 工作原则
- 成本透明：每一分成本都可拆解到一级科目
- 降本有依据：机会必须有量化单件节省与置信度
- 不臆造数字：所有数字来自种子/真实成本系统（事实锚点）
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[Cost Agent] Analyzing: {goal[:60]}...")

        products = await self.tools.get_product_costs()
        breakdown = await self.tools.get_cost_breakdown()
        savings = self.tools.SAVINGS

        avg_cost = round(sum(p["unit_cost"] for p in products) / len(products), 1)
        avg_margin = round(sum(p["margin_pct"] for p in products) / len(products), 1)
        over_target = [p for p in products if p["variance"] > 0]
        total_saving_per_unit = round(sum(s["saving_per_unit"] for s in savings), 1)

        actions_taken = []
        # 授权内行动：对超目标成本的产品生成降本任务（自动）
        for p in over_target:
            task = await self.tools.create_cost_reduction(f"{p['name']}降本")
            actions_taken.append({
                "type": "create_cost_reduction",
                "detail": f"为 {p['name']}（超目标 {p['variance']} 元）生成降本改善任务",
                "product_id": p["product_id"],
                "confidence": 0.83,
                "status": "auto_executed",
            })

        recommendations = self._generate_recommendations(products, over_target, savings, total_saving_per_unit)

        return {
            "status": "completed",
            "summary": (
                f"成本分析完成：{len(products)} 款产品平均单位成本 {avg_cost} 元，"
                f"平均毛利率 {avg_margin}%；{len(over_target)} 款超目标成本，"
                f"识别降本机会合计 {total_saving_per_unit} 元/片"
            ),
            "avg_unit_cost": avg_cost,
            "avg_margin_pct": avg_margin,
            "over_target_count": len(over_target),
            "total_saving_per_unit": total_saving_per_unit,
            "breakdown": breakdown,
            "products": products,
            "saving_opportunities": savings,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, products, over_target, savings, total_saving) -> list:
        recs = []
        if over_target:
            recs.append(f"📈 {len(over_target)} 款产品超目标成本，需重点降本：")
            for p in over_target:
                recs.append(f"   → {p['name']}：单位成本 {p['unit_cost']} 元（目标 {p['target_cost']}，超 {p['variance']} 元，毛利 {p['margin_pct']}%）")
        else:
            recs.append("✅ 全部产品成本均在目标范围内")
        recs.append(f"💰 降本机会合计 {total_saving} 元/片：")
        for s in sorted(savings, key=lambda x: -x["saving_per_unit"]):
            recs.append(f"   → {s['measure']}：{s['saving_per_unit']} 元/片（置信度 {int(s['confidence']*100)}%）")
        recs.append("📋 建议将降本空间纳入季度成本改善看板，按单件节省排序推进")
        return recs


cost_agent = CostAgent()
