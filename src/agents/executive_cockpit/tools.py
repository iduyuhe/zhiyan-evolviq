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

    # 应收账龄 seed（万元）：账龄分桶（财务决策维度，2026-08-02 补全）
    # 🔴 战略红线：只读推演（决策），不碰账本（记账/调账仍归 ERP）
    RECEIVABLES = [
        {"bucket": "30天内", "amount": 3200, "due_days": 20},
        {"bucket": "30-60天", "amount": 1500, "due_days": 45},
        {"bucket": "60-90天", "amount": 800, "due_days": 75},
        {"bucket": "90天以上", "amount": 600, "due_days": 120},  # 高风险逾期
    ]
    # 月度回款率（近 3 月，确定性规则输入）与月度运营支出（万元）
    COLLECTION_RATE = 0.72      # 月回款率（应收当月回收比例）
    MONTHLY_OPEX = 1900         # 月运营支出（含薪酬/采购/费用，万元）

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

    async def get_receivables(self) -> dict:
        """应收账龄分析（只读推演）：分桶 + 逾期占比 + 高风险判定。"""
        total = sum(r["amount"] for r in self.RECEIVABLES)
        overdue_90 = sum(r["amount"] for r in self.RECEIVABLES if r["due_days"] >= 90)
        overdue_60 = sum(r["amount"] for r in self.RECEIVABLES if r["due_days"] >= 60)
        return {
            "buckets": list(self.RECEIVABLES),
            "total_receivable": total,
            "overdue_90_amount": overdue_90,
            "overdue_90_ratio": round(overdue_90 / total * 100, 1) if total else 0.0,
            "overdue_60_ratio": round(overdue_60 / total * 100, 1) if total else 0.0,
            "risk_level": "high" if (overdue_90 / total if total else 0) >= 0.15 else "medium" if (overdue_90 / total if total else 0) >= 0.08 else "low",
            "note": "只读推演（决策），账本归 ERP 不在此层",
        }

    async def cash_forecast(self, months: int = 3) -> dict:
        """现金流 3 月滚动预测（确定性规则）：现金 + 月回款流入 - 月运营支出。

        事实锚点：全部来自 KPI/应收种子 + 确定性规则，无 LLM 推算。
        """
        cash = float(self.KPI["cash_position"])
        receivable_total = float(sum(r["amount"] for r in self.RECEIVABLES))
        monthly_inflow = round(receivable_total * self.COLLECTION_RATE / 3.0, 0)  # 3 月内回收
        series = []
        for i in range(1, months + 1):
            cash = round(cash + monthly_inflow - self.MONTHLY_OPEX, 0)
            series.append({"month": i, "closing_cash": cash})
        min_cash = min(s["closing_cash"] for s in series)
        return {
            "horizon_months": months,
            "monthly_inflow": monthly_inflow,
            "monthly_opex": self.MONTHLY_OPEX,
            "series": series,
            "min_cash": min_cash,
            "buffer_days_verdict": "紧张" if min_cash <= 0 else "充足" if min_cash >= self.KPI["days_of_cash"] * 0.5 * 30 else "需关注",
        }

    async def create_action_item(self, dept: str, issue: str) -> dict:
        """授权内行动：对超预算/欠产部门生成改善行动项。"""
        return {
            "task_id": f"ACT-{dept[:4]}",
            "dept": dept,
            "issue": issue,
            "note": "已生成经营改善行动项（授权内自动）",
        }
