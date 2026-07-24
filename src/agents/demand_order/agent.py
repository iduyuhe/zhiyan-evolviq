"""需求与订单 Agent——需求预测、订单履约、产销协同(S&OP)

企业级「经营大脑」第四部分：把市场需求与工厂供给对齐，识别交期风险，
在授权内做产销协同的供给再平衡，支撑接单与交付决策。

数据层：通过 DemandOrderTools 从种子数据加载（可切换真实 S&OP/ERP/CRM 系统）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.demand_order.tools import DemandOrderTools

logger = logging.getLogger(__name__)


class DemandOrderAgent(BaseAgent):
    """需求与订单 Agent"""

    name = "demand_order"
    description = "需求预测、订单履约率、未交付风险与产销协同(S&OP)再平衡"

    def __init__(self):
        self.tools = DemandOrderTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「需求与订单 Agent」，专注制造企业的销售运营计划(S&OP)与产销协同。

## 核心能力
1. 需求预测与已接订单对比（forecast vs booked）
2. 未交付(backlog)与订单满足率(fill_rate)核算
3. 交期风险识别（backlog 过高 / fill_rate 低于红线）
4. 产销协同：在授权内对供给做再平衡(reallocate_supply)，缓解瓶颈产品交付压力

## 工作原则
- 市场与工厂对齐：需求不是口号，要落到可交付的产能
- 风险前置：backlog 超阈值或 fill_rate 低于红线即预警
- 不臆造数字：所有数字来自种子/S&OP 系统（事实锚点）
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[Demand Agent] Analyzing: {goal[:60]}...")

        demand_items = await self.tools.get_demand_list()
        fulfillment = await self.tools.get_order_fulfillment()
        at_risk = fulfillment["at_risk_items"]

        actions_taken = []
        # 授权内行动：对存在交期风险的产品，将供给从满足率最高的产品再平衡过来（自动）
        if at_risk:
            # 找出满足率最高（余量最大）的产品作为供给来源
            donor = max(demand_items, key=lambda i: i["fill_rate"])
            for risk in at_risk:
                if risk["product_id"] == donor["product_id"]:
                    continue
                move_qty = round(min(risk["backlog"], donor["forecast"] * 0.1), 1)
                if move_qty <= 0:
                    continue
                task = await self.tools.reallocate_supply(
                    from_product=donor["name"], to_product=risk["name"], qty_wan=move_qty
                )
                actions_taken.append({
                    "type": "reallocate_supply",
                    "detail": f"将 {donor['name']} 约 {move_qty} 万片供给再平衡至 {risk['name']}（缓解交期风险）",
                    "product_id": risk["product_id"],
                    "confidence": 0.81,
                    "status": "auto_executed",
                })

        recommendations = self._generate_recommendations(demand_items, fulfillment, actions_taken)

        return {
            "status": "completed",
            "summary": (
                f"需求订单分析完成：本季需求 {fulfillment['total_forecast']} 万片，"
                f"已接订单 {fulfillment['total_booked']} 万片，未交付 {fulfillment['total_backlog']} 万片；"
                f"平均满足率 {fulfillment['avg_fill_rate']}%，{fulfillment['at_risk_count']} 款产品存在交期风险"
            ),
            "total_forecast": fulfillment["total_forecast"],
            "total_booked": fulfillment["total_booked"],
            "total_backlog": fulfillment["total_backlog"],
            "avg_fill_rate": fulfillment["avg_fill_rate"],
            "at_risk_count": fulfillment["at_risk_count"],
            "demand_items": demand_items,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, demand_items, fulfillment, actions_taken) -> list:
        recs = []
        recs.append(
            f"📊 本季需求 {fulfillment['total_forecast']} 万片，已接 {fulfillment['total_booked']} 万片，"
            f"平均满足率 {fulfillment['avg_fill_rate']}%（红线 90%）"
        )
        if fulfillment["at_risk_count"]:
            recs.append(f"⚠️ {fulfillment['at_risk_count']} 款产品存在交期风险：")
            for i in fulfillment["at_risk_items"]:
                recs.append(
                    f"   → {i['name']}：未交付 {i['backlog']} 万片，满足率 {i['fill_rate']}%"
                )
        else:
            recs.append("✅ 全部产品满足率在红线之上，交付可控")
        if actions_taken:
            recs.append("🔄 已生成产销协同供给再平衡建议（授权内自动）：")
            for a in actions_taken:
                recs.append(f"   → {a['detail']}")
        recs.append("📋 建议将 S&OP 评审结论纳入月度产销协同会，按风险等级排序推进")
        return recs


demand_agent = DemandOrderAgent()
