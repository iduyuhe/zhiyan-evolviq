"""经营驾驶舱 Agent——经营 KPI、损益、现金流、预算执行、产出看板

企业级「经营决策大脑」第七部分：将季度财务 KPI、部门预算执行、产出 vs 计划
汇总为一张经营决策看板，识别超预算/欠产环节并授权内自动生成改善项。

数据层：通过 ExecutiveCockpitTools 从种子数据加载（可切换真实 ERP/BI 系统）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.executive_cockpit.tools import ExecutiveCockpitTools

logger = logging.getLogger(__name__)


class ExecutiveCockpitAgent(BaseAgent):
    """经营驾驶舱 Agent"""

    name = "executive_cockpit"
    description = "经营 KPI 看板、损益、现金流、预算执行、产出 vs 计划 —— 全厂决策支持"

    def __init__(self):
        self.tools = ExecutiveCockpitTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「经营驾驶舱 Agent」，制造企业高管的经营决策仪表盘。

## 核心能力
1. 财务看板：季度营收/成本/毛利/净利/现金流
2. 预算执行：部门级预算 vs 实际差异，识别超预算与节省
3. 产出追踪：各产品产出 vs 计划，识别欠产环节
4. 授权内自动改善：对超预算或欠产部门生成改善行动项(create_action_item)

## 工作原则
- 全局视角：不替代业务 Agent，聚焦跨部门汇聚与趋势
- 数字说话：所有数字来自 ERP/BI 系统（事实锚点）
- 经营导向：每一行动都有量化依据，不凭空建议
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[Executive Agent] Analyzing: {goal[:60]}...")

        kpi = await self.tools.get_kpi_dashboard()
        budgets = await self.tools.get_budget_utilization()
        production = await self.tools.get_production_summary()

        net_margin = round(kpi["net_profit"] / kpi["revenue_quarter"] * 100, 1) if kpi["revenue_quarter"] else 0.0
        overspend = [b for b in budgets if b["status"] == "overspend"]
        prod_pct = round(production["actual_total"] / production["plan_total"] * 100, 1) if production["plan_total"] else 0.0

        actions_taken = []
        # 授权内行动：对超预算部门生成改善行动项
        for b in overspend:
            task = await self.tools.create_action_item(b["dept"], f"超预算 {b['variance']} 万元，{b['note']}")
            actions_taken.append({
                "type": "create_action_item",
                "detail": f"为 {b['dept']}（超预算 {b['variance']} 万元，{b['note']}）生成改善任务",
                "dept": b["dept"],
                "confidence": 0.82,
                "status": "auto_executed",
            })

        recommendations = self._generate_recommendations(kpi, budgets, production, prod_pct, overspend, actions_taken)

        return {
            "status": "completed",
            "summary": (
                f"经营分析完成：季度营收 {kpi['revenue_quarter']} 万元，毛利率 {kpi['gross_margin_pct']}%，"
                f"净利率 {net_margin}%，现金余额 {kpi['cash_position']} 万元（{kpi['days_of_cash']} 天）；"
                f"产出完成率 {prod_pct}%，{len(overspend)} 个部门超预算"
            ),
            "revenue_quarter": kpi["revenue_quarter"],
            "gross_margin_pct": kpi["gross_margin_pct"],
            "net_margin_pct": net_margin,
            "cash_position": kpi["cash_position"],
            "days_of_cash": kpi["days_of_cash"],
            "order_backlog_value": kpi["order_backlog_value"],
            "prod_completion_pct": prod_pct,
            "overspend_depts": len(overspend),
            "budgets": budgets,
            "production": production,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, kpi, budgets, production, prod_pct, overspend, actions_taken) -> list:
        recs = []
        recs.append(
            f"🏢 营收 {kpi['revenue_quarter']} 万元，毛利 {kpi['gross_margin_pct']}%，净利 {kpi['net_profit']} 万元"
        )
        recs.append(
            f"💰 现金余额 {kpi['cash_position']} 万元（可支撑 {kpi['days_of_cash']} 天），未交付订单 {kpi['order_backlog_value']} 万元"
        )
        recs.append(f"🏭 产出完成率 {prod_pct}%（计划 {production['plan_total']} 万片 / 实际 {production['actual_total']} 万片）")
        if overspend:
            recs.append(f"📊 {len(overspend)} 个部门超预算：")
            for b in overspend:
                recs.append(f"   → {b['dept']}：预算 {b['plan']} 万，实际 {b['actual']} 万��{b['util_pct']}%），{b['note']}")
        else:
            recs.append("✅ 全部部门在预算范围内")
        if actions_taken:
            recs.append("🔄 已生成改善行动项（授权内自动）：")
            for a in actions_taken:
                recs.append(f"   → {a['detail']}")
        recs.append("📋 建议将经营数据纳入月度经营分析会，按偏差幅度排序跟进")
        return recs


executive_agent = ExecutiveCockpitAgent()
