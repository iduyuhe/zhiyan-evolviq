"""仓储与物流 Agent 工具层——库存健康、库容、物流时效与在途（确定性种子数据）

数据层：内置物料库存与物流路线种子，可切换真实 WMS/TMS/ERP 系统。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""

from __future__ import annotations


class WMSLogisticsTools:
    """仓储与物流工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 关键物料库存种子（stock_value_wan=库存金额万元；safety_wan=安全库存金额万元）
    INVENTORY = [
        {"material_id": "M-WAFER", "name": "12寸晶圆", "stock_value_wan": 1500, "safety_wan": 600,
         "turnover": 12, "abc": "A", "obsolete_wan": 0},
        {"material_id": "M-PR", "name": "光刻胶", "stock_value_wan": 320, "safety_wan": 200,
         "turnover": 5, "abc": "A", "obsolete_wan": 60},
        {"material_id": "M-CER", "name": "陶瓷基板", "stock_value_wan": 90, "safety_wan": 100,
         "turnover": 8, "abc": "B", "obsolete_wan": 18},
        {"material_id": "M-PASS", "name": "被动元件", "stock_value_wan": 90, "safety_wan": 60,
         "turnover": 22, "abc": "C", "obsolete_wan": 5},
    ]

    # 物流路线种子（lead_time=时效天；on_time_rate=准时率%）
    LOGISTICS = [
        {"route": "华东仓→SMT-L01", "lead_time": 1.5, "on_time_rate": 96},
        {"route": "华南供应商→华东仓", "lead_time": 4.0, "on_time_rate": 88},
        {"route": "进口特气→厂内", "lead_time": 9.0, "on_time_rate": 82},
        {"route": "成品→客户", "lead_time": 2.0, "on_time_rate": 94},
    ]

    async def get_inventory(self) -> list[dict]:
        out = []
        for m in self.INVENTORY:
            below = m["stock_value_wan"] < m["safety_wan"]
            out.append({
                "material_id": m["material_id"],
                "name": m["name"],
                "stock_value_wan": m["stock_value_wan"],
                "safety_wan": m["safety_wan"],
                "turnover": m["turnover"],
                "abc": m["abc"],
                "obsolete_wan": m["obsolete_wan"],
                "below_safety": below,
            })
        return out

    async def get_logistics(self) -> list[dict]:
        out = []
        for r in self.LOGISTICS:
            status = "slow" if r["lead_time"] > 5 else ("delay" if r["on_time_rate"] < 85 else "ok")
            out.append({
                "route": r["route"],
                "lead_time": r["lead_time"],
                "on_time_rate": r["on_time_rate"],
                "status": status,
            })
        return out

    async def create_replenishment(self, material: str, qty_wan: float) -> dict:
        """授权内行动：对低于安全库存的物料生成补货任务（确定性）。"""
        return {
            "task_id": f"WMS-RPL-{material}",
            "material": material,
            "qty_wan": qty_wan,
            "note": "已生成补货申请（授权内自动）",
        }

    async def reroute_shipment(self, route: str, new_route: str) -> dict:
        """需审批行动：物流改道（占位，实际触发人工审批）。"""
        return {
            "task_id": f"WMS-REROUTE-{route}",
            "route": route,
            "new_route": new_route,
            "note": "物流改道建议，待人工审批",
        }
