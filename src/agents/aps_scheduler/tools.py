"""计划排程 Agent 工具层——APS 调度、产能负荷、交期承诺（确定性种子数据）

数据层：内置半导体/SMT 工厂的工单与产能种子，可切换真实 MES/ERP。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""


class APSTools:
    """APS 计划排程工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 工单种子（due 为交期；promised 为系统承诺交期；slack_days 为缓冲天数，<0 表示逾期风险）
    ORDERS = [
        {"order_id": "SO-2401", "product": "28nm 逻辑芯片", "qty": 5000, "due": "2026-08-01", "promised": "2026-07-30", "slack_days": 4, "priority": "normal"},
        {"order_id": "SO-2402", "product": "功率器件", "qty": 3000, "due": "2026-08-05", "promised": "2026-08-03", "slack_days": 2, "priority": "normal"},
        {"order_id": "SO-2403", "product": "BMS 控制板", "qty": 8000, "due": "2026-07-28", "promised": "2026-07-29", "slack_days": -1, "priority": "high"},
        {"order_id": "SO-2404", "product": "摄像头模组", "qty": 12000, "due": "2026-08-10", "promised": "2026-08-08", "slack_days": 6, "priority": "normal"},
        {"order_id": "SO-2405", "product": "车规 MCU", "qty": 6000, "due": "2026-08-03", "promised": "2026-08-02", "slack_days": 1, "priority": "high"},
        {"order_id": "SO-2406", "product": "工业网关", "qty": 4000, "due": "2026-08-12", "promised": "2026-08-10", "slack_days": 8, "priority": "normal"},
    ]

    # 工作中心/产线产能种子（capacity_h=计划工时，load_h=已排负荷工时）
    WORK_CENTERS = [
        {"wc_id": "WC-SMT1", "name": "SMT 产线1", "capacity_h": 168, "load_h": 150},
        {"wc_id": "WC-SMT2", "name": "SMT 产线2", "capacity_h": 168, "load_h": 162},
        {"wc_id": "WC-ASSY", "name": "组装测试线", "capacity_h": 120, "load_h": 84},
        {"wc_id": "WC-TEST", "name": "成品测试线", "capacity_h": 120, "load_h": 96},
    ]

    async def get_order_list(self) -> list[dict]:
        return [dict(o) for o in self.ORDERS]

    async def get_work_centers(self) -> list[dict]:
        out = []
        for wc in self.WORK_CENTERS:
            util = round(wc["load_h"] / wc["capacity_h"] * 100, 1)
            out.append({
                "wc_id": wc["wc_id"],
                "name": wc["name"],
                "capacity_h": wc["capacity_h"],
                "load_h": wc["load_h"],
                "utilization": util,
                "status": "critical" if util >= 95 else "warning" if util >= 85 else "good",
            })
        return out

    async def rebalance_schedule(self, from_wc: str, to_wc: str, qty: int) -> dict:
        """在授权范围内生成产能再平衡建议（行动落地占位）。"""
        return {
            "task_id": f"RB-{from_wc}-{to_wc}",
            "from_wc": from_wc,
            "to_wc": to_wc,
            "qty": qty,
            "note": f"将 {qty} 片负荷从 {from_wc} 转移到 {to_wc}，缓解瓶颈",
        }
