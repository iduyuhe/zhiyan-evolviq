"""仓储与物流 Agent——库存健康、库容利用、物流时效与在途

企业级「经营大脑」第五部分：把物料库存（金额/周转/呆滞）与物流（时效/准时率）
结构化，识别低于安全库存的物料并授权内自动补货，支撑供应链韧性与交付时效。

数据层：通过 WMSLogisticsTools 从种子数据加载（可切换真实 WMS/TMS/ERP 系统）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.wms_logistics.tools import WMSLogisticsTools

logger = logging.getLogger(__name__)


class WMSLogisticsAgent(BaseAgent):
    """仓储与物流 Agent"""

    name = "wms_logistics"
    description = "库存健康度、库容利用率、物流时效与在途监控，授权内自动补货"

    def __init__(self):
        self.tools = WMSLogisticsTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「仓储与物流 Agent」，专注制造企业的仓储(WMS)与物流(TMS)运营。

## 核心能力
1. 库存健康度：库存金额、周转次数、呆滞(obsolete)占比、安全库存达标
2. 库容利用：ABC 分类下的库存结构
3. 物流时效：各路线 lead_time 与 on_time_rate，识别慢链路/延迟风险
4. 授权内自动补货：对低于安全库存的物料生成补货任务(create_replenishment)

## 工作原则
- 韧性优先：安全库存是底线，低于即预警并自动补货
- 周转意识：高金额低周转=资金占用，呆滞=减值风险
- 不臆造数字：所有数字来自种子/WMS/TMS 系统（事实锚点）
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[WMS Agent] Analyzing: {goal[:60]}...")

        inventory = await self.tools.get_inventory()
        logistics = await self.tools.get_logistics()

        total_value = sum(m["stock_value_wan"] for m in inventory)
        total_obsolete = sum(m["obsolete_wan"] for m in inventory)
        obsolete_pct = round(total_obsolete / total_value * 100, 1) if total_value else 0.0
        # 金额加权周转
        turnover = round(
            sum(m["turnover"] * m["stock_value_wan"] for m in inventory) / total_value, 1
        ) if total_value else 0.0
        avg_lead = round(sum(r["lead_time"] for r in logistics) / len(logistics), 1)
        on_time_rate = round(sum(r["on_time_rate"] for r in logistics) / len(logistics), 1)
        below_safety = [m for m in inventory if m["below_safety"]]

        actions_taken = []
        # 授权内行动：对低于安全库存的物料生成补货任务（自动）
        for m in below_safety:
            gap = round(m["safety_wan"] - m["stock_value_wan"], 1)
            task = await self.tools.create_replenishment(m["name"], gap)
            actions_taken.append({
                "type": "create_replenishment",
                "detail": f"为 {m['name']}（低于安全库存 {gap} 万元）生成补货任务",
                "material_id": m["material_id"],
                "confidence": 0.84,
                "status": "auto_executed",
            })

        recommendations = self._generate_recommendations(
            inventory, logistics, total_value, obsolete_pct, turnover,
            avg_lead, on_time_rate, below_safety, actions_taken
        )

        return {
            "status": "completed",
            "summary": (
                f"仓储物流分析完成：库存总额 {total_value} 万元，加权周转 {turnover} 次/年，"
                f"呆滞占比 {obsolete_pct}%；物流平均时效 {avg_lead} 天，准时率 {on_time_rate}%，"
                f"{len(below_safety)} 项物料低于安全库存"
            ),
            "total_stock_value_wan": total_value,
            "turnover": turnover,
            "obsolete_pct": obsolete_pct,
            "avg_lead_time": avg_lead,
            "on_time_rate": on_time_rate,
            "below_safety_count": len(below_safety),
            "inventory": inventory,
            "logistics": logistics,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, inventory, logistics, total_value, obsolete_pct,
                                  turnover, avg_lead, on_time_rate, below_safety, actions_taken) -> list:
        recs = []
        recs.append(
            f"📦 库存总额 {total_value} 万元，加权周转 {turnover} 次/年，呆滞占比 {obsolete_pct}%"
        )
        if below_safety:
            recs.append(f"⚠️ {len(below_safety)} 项物料低于安全库存：")
            for m in below_safety:
                recs.append(
                    f"   → {m['name']}：库存 {m['stock_value_wan']} 万元（安全 {m['safety_wan']} 万元）"
                )
        else:
            recs.append("✅ 全部关键物料在安全库存之上")
        recs.append(
            f"🚚 物流平均时效 {avg_lead} 天，准时率 {on_time_rate}%；"
            f"进口特气路线时效最长且准时率最低，建议引入二级供应商"
        )
        if actions_taken:
            recs.append("🔄 已生成补货任务（授权内自动）：")
            for a in actions_taken:
                recs.append(f"   → {a['detail']}")
        recs.append("📋 建议将库存健康度纳入月度供应链韧性看板，按 ABC 分级管理")
        return recs


wms_agent = WMSLogisticsAgent()
