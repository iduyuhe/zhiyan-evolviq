"""经营驾驶舱 Agent 工具层——经营KPI、损益、现金流、预算执行（确定性种子数据）

数据层：内置季度财务KPI、预算执行、产出 vs 计划种子，可切换真实 ERP/BI 系统。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""

from __future__ import annotations


class ExecutiveCockpitTools:
    """经营驾驶舱工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 本季度财务KPI种子（万元）
    KPI = {
        "revenue_quarter": 12000,          # 季度营收
        "cogs": 8400,                      # 销售成本
        "gross_margin_pct": 30.0,          # 毛利率 %
        "operating_expense": 2400,         # 运营费用
        "net_profit": 800,                 # 净利润
        "cash_position": 3600,             # 现金余额
        "days_of_cash": 45,                # 现金周转天数
        "order_backlog_value": 5200,       # 未交付订单金额
    }

    # 预算执行种子（万元）：部门级 plan vs actual
    BUDGETS = [
        {"dept": "生产部", "plan": 5000, "actual": 5200, "note": "超预算（加班费+材料涨价）"},
        {"dept": "研发部", "plan": 1500, "actual": 1420, "note": "节省（测试外包减少）"},
        {"dept": "销售部", "plan": 800, "actual": 840, "note": "超预算（展会增加）"},
        {"dept": "质量部", "plan": 400, "actual": 380, "note": "在预算内"},
        {"dept": "设备维护", "plan": 600, "actual": 720, "note": "超预算（紧急维修增加）"},
        {"dept": "管理费", "plan": 300, "actual": 290, "note": "在预算内"},
    ]

    # 产出 vs 计划（万片，本季累计）
    PRODUCTION = {
        "plan_total": 350,
        "actual_total": 338,
        "by_product": [
            {"product": "28nm 逻辑芯片", "plan": 120, "actual": 115},
            {"product": "功率器件", "plan": 100, "actual": 98},
            {"product": "BMS 控制板", "plan": 75, "actual": 70},
            {"product": "摄像头模组", "plan": 55, "actual": 55},
        ],
    }

    async def get_kpi_dashboard(self) -> dict:
        return dict(self.KPI)

    async def get_budget_utilization(self) -> list[dict]:
        out = []
        for b in self.BUDGETS:
            pct = round(b["actual"] / b["plan"] * 100, 1) if b["plan"] else 0.0
            status = "overspend" if b["actual"] > b["plan"] else "underspend" if b["actual"] < b["plan"] else "on_target"
            out.append({
                "dept": b["dept"],
                "plan": b["plan"],
                "actual": b["actual"],
                "util_pct": pct,
                "variance": round(b["actual"] - b["plan"], 1),
                "status": status,
                "note": b["note"],
            })
        return out

    async def get_production_summary(self) -> dict:
        return dict(self.PRODUCTION)

    async def create_action_item(self, dept: str, issue: str) -> dict:
        """授权内行动：对超预算/欠产部门生成改善行动项。"""
        return {
            "task_id": f"ACT-{dept[:4]}",
            "dept": dept,
            "issue": issue,
            "note": "已生成经营改善行动项（授权内自动）",
        }
