"""需求与订单 Agent 工具层——需求预测、订单履约、产销协同（确定性种子数据）

数据层：内置本季需求/订单/未交付种子，可切换真实 S&OP/ERP/CRM 系统。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""

from __future__ import annotations


class DemandOrderTools:
    """需求与订单工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 本季需求与订单种子（单位：万片）；forecast=需求预测 booked=已接订单 backlog=未交付
    DEMAND = [
        {"product_id": "P-28NM", "name": "28nm 逻辑芯片", "forecast": 120, "booked": 118, "backlog": 22},
        {"product_id": "P-PWR", "name": "功率器件", "forecast": 80, "booked": 76, "backlog": 10},
        {"product_id": "P-BMS", "name": "BMS 控制板", "forecast": 60, "booked": 58, "backlog": 15},
        {"product_id": "P-CAM", "name": "摄像头模组", "forecast": 50, "booked": 48, "backlog": 8},
    ]

    # 履约缓冲阈值（万片）：未交付超过该值视为交期风险
    BACKLOG_RISK_THRESHOLD = 12.0
    # 订单满足率红线（%）：低于该值视为履约风险
    FILL_RATE_RED_LINE = 90.0

    async def get_demand_list(self) -> list[dict]:
        """各产品需求/订单/未交付与履约率（确定性推导）。"""
        out = []
        for d in self.DEMAND:
            fill_rate = round(d["booked"] / d["forecast"] * 100, 1) if d["forecast"] else 0.0
            at_risk = (
                d["backlog"] > self.BACKLOG_RISK_THRESHOLD
                or fill_rate < self.FILL_RATE_RED_LINE
            )
            out.append({
                "product_id": d["product_id"],
                "name": d["name"],
                "forecast": d["forecast"],
                "booked": d["booked"],
                "backlog": d["backlog"],
                "fill_rate": fill_rate,
                "at_risk": at_risk,
            })
        return out

    async def get_order_fulfillment(self) -> dict:
        """全厂订单履约汇总。"""
        items = await self.get_demand_list()
        total_forecast = sum(i["forecast"] for i in items)
        total_booked = sum(i["booked"] for i in items)
        total_backlog = sum(i["backlog"] for i in items)
        avg_fill = round(sum(i["fill_rate"] for i in items) / len(items), 1)
        at_risk = [i for i in items if i["at_risk"]]
        return {
            "total_forecast": total_forecast,
            "total_booked": total_booked,
            "total_backlog": total_backlog,
            "avg_fill_rate": avg_fill,
            "at_risk_count": len(at_risk),
            "at_risk_items": at_risk,
        }

    async def reallocate_supply(self, from_product: str, to_product: str, qty_wan: float) -> dict:
        """授权内行动：将产能/供给在两类产品间再平衡（确定性，不改写业务数字）。"""
        return {
            "task_id": f"SOP-REALLOC-{from_product}-{to_product}",
            "from_product": from_product,
            "to_product": to_product,
            "qty_wan": qty_wan,
            "note": "已生成产销协同供给再平衡建议",
        }
