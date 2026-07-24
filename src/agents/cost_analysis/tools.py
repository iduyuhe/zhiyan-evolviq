"""制造成本 Agent 工具层——单位成本拆解、降本机会、报价支撑（确定性种子数据）

数据层：内置产品成本结构与费率种子，可切换真实 ERP/成本系统。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""


class CostAnalysisTools:
    """制造成本工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 产品成本结构种子（元/片）；target_cost=目标成本；price=售价
    PRODUCTS = [
        {"product_id": "P-28NM", "name": "28nm 逻辑芯片", "bom": 120, "labor": 35, "equipment": 60,
         "energy": 18, "scrap": 22, "target": 230, "price": 320},
        {"product_id": "P-PWR", "name": "功率器件", "bom": 88, "labor": 28, "equipment": 44,
         "energy": 15, "scrap": 16, "target": 180, "price": 250},
        {"product_id": "P-BMS", "name": "BMS 控制板", "bom": 95, "labor": 22, "equipment": 30,
         "energy": 12, "scrap": 14, "target": 160, "price": 210},
        {"product_id": "P-CAM", "name": "摄像头模组", "bom": 140, "labor": 18, "equipment": 26,
         "energy": 9, "scrap": 11, "target": 190, "price": 268},
    ]

    # 降本机会库（确定性）：measure + 年化节省(元/片) + 类别
    SAVINGS = [
        {"measure": "关键物料国产替代", "saving_per_unit": 8.0, "category": "bom", "confidence": 0.85},
        {"measure": "良率提升 1.5pp（减少 scrap）", "saving_per_unit": 6.0, "category": "scrap", "confidence": 0.8},
        {"measure": "能耗优化（空压/照明）", "saving_per_unit": 3.0, "category": "energy", "confidence": 0.82},
        {"measure": "SMED 换线提速（摊薄设备成本）", "saving_per_unit": 4.0, "category": "equipment", "confidence": 0.78},
    ]

    async def get_product_costs(self) -> list[dict]:
        out = []
        for p in self.PRODUCTS:
            unit = p["bom"] + p["labor"] + p["equipment"] + p["energy"] + p["scrap"]
            variance = round(unit - p["target"], 1)
            margin = round((p["price"] - unit) / p["price"] * 100, 1)
            out.append({
                "product_id": p["product_id"],
                "name": p["name"],
                "unit_cost": unit,
                "target_cost": p["target"],
                "variance": variance,
                "margin_pct": margin,
                "bom": p["bom"], "labor": p["labor"], "equipment": p["equipment"],
                "energy": p["energy"], "scrap": p["scrap"],
            })
        return out

    async def get_cost_breakdown(self) -> list[dict]:
        """全厂加权成本结构（按各产品单位成本均值拆解）。"""
        products = await self.get_product_costs()
        cats = {"bom": 0.0, "labor": 0.0, "equipment": 0.0, "energy": 0.0, "scrap": 0.0}
        for p in products:
            cats["bom"] += p["bom"]
            cats["labor"] += p["labor"]
            cats["equipment"] += p["equipment"]
            cats["energy"] += p["energy"]
            cats["scrap"] += p["scrap"]
        n = len(products)
        total = sum(cats.values())
        return [
            {"category": k, "amount": round(v / n, 1), "pct": round(v / total * 100, 1)}
            for k, v in cats.items()
        ]

    async def create_cost_reduction(self, measure: str) -> dict:
        return {"task_id": f"CR-{measure[:6]}", "measure": measure, "note": "已生成降本改善任务"}
