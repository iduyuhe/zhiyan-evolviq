"""计划排程 Agent (APS)——生产排程、产能负荷、交期承诺、工单优先级

企业级「经营大脑」第一部分：把制造执行层的产能与订单需求对齐，输出
可承诺交期(CTP)、产能负荷与瓶颈识别，并在授权范围内给出再平衡/催交建议。

数据层：通过 APSTools 从种子数据加载（可切换真实 MES/ERP）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.aps_scheduler.tools import APSTools

logger = logging.getLogger(__name__)


class APSAgent(BaseAgent):
    """计划排程 Agent"""

    name = "aps_scheduler"
    description = "生产排程、产能负荷、交期承诺与工单优先级优化"

    def __init__(self):
        self.tools = APSTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「计划排程 Agent」，专注制造企业的生产计划与排程(APS)。

## 核心能力
1. 产能负荷计算（工作中心可用率 = 已排负荷 / 计划产能）
2. 交期承诺(CTP)：基于产能与工单缓冲评估能否准时交付
3. 瓶颈工作中心识别（负荷率最高的环节）
4. 工单优先级调度（按交期紧迫度+客户等级）
5. 产能再平衡建议（在授权范围内将负荷从高负荷中心转移到低负荷中心）

## 工作原则
- 交期优先：逾期风险(slack<0)与紧交期(slack<=1)工单优先调度
- 负荷均衡：单工作中心负荷率不宜超过 85%（世界级制造水平）
- 数据驱动：每个结论必须有量化数据支撑
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[APS Agent] Analyzing: {goal[:60]}...")

        orders = await self.tools.get_order_list()
        work_centers = await self.tools.get_work_centers()

        total_cap = sum(w["capacity_h"] for w in work_centers)
        total_load = sum(w["load_h"] for w in work_centers)
        avg_util = round(total_load / total_cap * 100, 1)
        bottleneck = max(work_centers, key=lambda w: w["utilization"])

        # 交期风险：slack<0 逾期，<=1 紧交期
        on_time = sum(1 for o in orders if o["slack_days"] >= 0)
        on_time_rate = round(on_time / len(orders) * 100, 1)
        at_risk = [o for o in orders if o["slack_days"] < 2]

        # 授权内行动：再平衡（从高负荷中心转移到低负荷）+ 催交紧交期工单
        actions_taken = []
        low_wc = min(work_centers, key=lambda w: w["utilization"])
        if bottleneck["utilization"] >= 85 and low_wc["wc_id"] != bottleneck["wc_id"]:
            rb = await self.tools.rebalance_schedule(bottleneck["wc_id"], low_wc["wc_id"], 2000)
            actions_taken.append({
                "type": "rebalance_schedule",
                "detail": f"将 2000 片负荷从 {bottleneck['name']} 再平衡至 {low_wc['name']}",
                "from_wc": bottleneck["wc_id"],
                "to_wc": low_wc["wc_id"],
                "qty": 2000,
                "confidence": 0.84,
                "status": "auto_executed",
            })
        for o in at_risk:
            actions_taken.append({
                "type": "expedite_order",
                "detail": f"催交 {o['order_id']}({o['product']})，缓冲仅 {o['slack_days']} 天",
                "order_id": o["order_id"],
                "confidence": 0.9,
                "status": "pending_approval",
            })

        recommendations = self._generate_recommendations(orders, work_centers, bottleneck, at_risk)

        return {
            "status": "completed",
            "summary": (
                f"APS 分析完成：{len(orders)} 张工单，综合产能负荷 {avg_util}%，"
                f"瓶颈 {bottleneck['name']}({bottleneck['utilization']}%)；交期准时率 {on_time_rate}%，"
                f"{len(at_risk)} 张工单存在交期风险"
            ),
            "avg_utilization": avg_util,
            "total_capacity_h": total_cap,
            "total_load_h": total_load,
            "on_time_rate": on_time_rate,
            "bottleneck_wc": bottleneck["name"],
            "bottleneck_util": bottleneck["utilization"],
            "orders": orders,
            "at_risk_count": len(at_risk),
            "work_centers": work_centers,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, orders, work_centers, bottleneck, at_risk) -> list:
        recs = []
        recs.append(f"🚧 瓶颈工作中心：{bottleneck['name']} 负荷率 {bottleneck['utilization']}%（目标≤85%）")
        if bottleneck["utilization"] >= 85:
            low = min(work_centers, key=lambda w: w["utilization"])
            recs.append(f"   → 建议将部分负荷再平衡至 {low['name']}（当前 {low['utilization']}%）")
        if at_risk:
            recs.append(f"⏰ 交期风险工单 {len(at_risk)} 张，建议优先排产并催交：")
            for o in at_risk:
                flag = "🔴逾期风险" if o["slack_days"] < 0 else "🟠紧交期"
                recs.append(f"   → {o['order_id']} {o['product']}：{flag}（缓冲 {o['slack_days']} 天）")
        else:
            recs.append("✅ 当前工单交期均在可控范围内")
        recs.append("📋 建议每日晨会基于产能负荷看板重排优先级，聚焦瓶颈与紧交期工单")
        return recs


aps_agent = APSAgent()
