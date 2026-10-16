"""计划排程 Agent 工具层——APS 调度、产能负荷、交期承诺（确定性种子数据）

数据层：内置半导体/SMT 工厂的工单与产能种子，可切换真实 MES/ERP。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。

造船增强（2026-10-16）：在保持通用离散制造路径不变的前提下，新增
「造船感知」种子与分析方法。造船排产与离散制造本质不同——船坞是不可复制
的瓶颈闸门、壳舾涂一体化、托盘齐套耦合、多船型并行、设计变更高频。
全部造船数字为匿名化演示种子（示意，不指向任何真实船厂业绩）。
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

    # ============ 造船感知种子（匿名化演示，不指向真实船厂业绩） ============
    # 船坞窗口：船坞是不可复制的瓶颈资源，坞期延误沿合拢→下水→码头连锁放大
    SHIP_DOCKS = [
        {"dock_id": "DOCK-A", "name": "一号干船坞", "current_hull": "HULL-001", "next_hull": "HULL-002",
         "current_progress": 78, "window_close": "2026-11-20", "next_window_open": "2026-11-25",
         "next_tray_readiness": 64, "status": "occupied"},
        {"dock_id": "DOCK-B", "name": "二号浮船坞", "current_hull": "HULL-003", "next_hull": "HULL-004",
         "current_progress": 91, "window_close": "2026-10-30", "next_window_open": "2026-11-03",
         "next_tray_readiness": 88, "status": "occupied"},
        {"dock_id": "DOCK-C", "name": "舾装码头", "current_hull": "HULL-005", "next_hull": "HULL-006",
         "current_progress": 55, "window_close": "2027-01-15", "next_window_open": "2027-01-20",
         "next_tray_readiness": 41, "status": "occupied"},
    ]

    # 多船型并行：同一批关键工种同时服务多艘不同船型，资源冲突是常态
    SHIP_HULLS = [
        {"hull_id": "HULL-001", "type": "VLCC 油轮", "stage": "总段合拢", "planned_days": 120, "actual_days": 128, "blocking": "tray"},
        {"hull_id": "HULL-002", "type": "大型集装箱船", "stage": "分段建造", "planned_days": 95, "actual_days": 90, "blocking": "none"},
        {"hull_id": "HULL-003", "type": "LNG 液化气船", "stage": "下水前收尾", "planned_days": 70, "actual_days": 73, "blocking": "paint"},
        {"hull_id": "HULL-004", "type": "支线集装箱船", "stage": "分段建造", "planned_days": 80, "actual_days": 84, "blocking": "weld"},
        {"hull_id": "HULL-005", "type": "汽车运输船(PCTC)", "stage": "码头舾装", "planned_days": 150, "actual_days": 162, "blocking": "tray"},
        {"hull_id": "HULL-006", "type": "邮轮", "stage": "分段建造", "planned_days": 110, "actual_days": 105, "blocking": "none"},
    ]

    # 托盘齐套：后行窝工 80% 源于托盘不齐，而非工人不够（物料-工序耦合）
    SHIP_TRAYS = [
        {"tray_id": "U-001", "scope": "机舱底层舾装", "required": 42, "ready": 38, "due_hull": "HULL-001"},
        {"tray_id": "U-002", "scope": "上层建筑管系", "required": 56, "ready": 21, "due_hull": "HULL-005"},
        {"tray_id": "U-003", "scope": "住舱单元", "required": 33, "ready": 30, "due_hull": "HULL-003"},
        {"tray_id": "U-004", "scope": "轴系舾装", "required": 28, "ready": 27, "due_hull": "HULL-002"},
        {"tray_id": "U-005", "scope": "甲板机械", "required": 47, "ready": 19, "due_hull": "HULL-005"},
        {"tray_id": "U-006", "scope": "液货系统", "required": 39, "ready": 35, "due_hull": "HULL-003"},
    ]

    # 关键工种负荷：跨船型并行导致焊工/装配/涂装冲突
    SHIP_WORKFORCE = [
        {"trade": "焊工", "capacity_h": 960, "load_h": 1120, "across_hulls": ["HULL-001", "HULL-004", "HULL-006"]},
        {"trade": "装配工", "capacity_h": 880, "load_h": 792, "across_hulls": ["HULL-002", "HULL-003", "HULL-005"]},
        {"trade": "涂装工", "capacity_h": 640, "load_h": 580, "across_hulls": ["HULL-003", "HULL-005"]},
        {"trade": "管系工", "capacity_h": 720, "load_h": 805, "across_hulls": ["HULL-001", "HULL-005"]},
    ]

    # 设计变更(ECN)：计划脆弱，需动态再平衡而非一次排定
    SHIP_ECN = [
        {"ecn_id": "ECN-2207", "hull": "HULL-001", "scope": "机舱通风管路", "impact_days": 5, "status": "pending"},
        {"ecn_id": "ECN-2208", "hull": "HULL-005", "scope": "住舱防火分隔", "impact_days": 8, "status": "pending"},
        {"ecn_id": "ECN-2209", "hull": "HULL-003", "scope": "液货泵舱", "impact_days": 3, "status": "approved"},
    ]

    # ============================ 通用方法 ============================

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

    # ============================ 造船感知方法 ============================

    async def get_ship_docks(self) -> list[dict]:
        out = []
        for d in self.SHIP_DOCKS:
            # 船坞就绪度 = 当前进度对窗口闭合的达成度 × 下一船型托盘齐套度
            progress_gap = max(0, 100 - d["current_progress"])
            window_readiness = round(d["current_progress"] * 0.6 + d["next_tray_readiness"] * 0.4, 1)
            out.append({
                **d,
                "window_readiness": window_readiness,
                "progress_gap": progress_gap,
                "risk": "high" if window_readiness < 70 else "mid" if window_readiness < 85 else "low",
            })
        return out

    async def get_ship_hulls(self) -> list[dict]:
        out = []
        for h in self.SHIP_HULLS:
            deviation = round((h["actual_days"] - h["planned_days"]) / h["planned_days"] * 100, 1)
            out.append({
                **h,
                "takt_deviation_pct": deviation,
                "status": "behind" if deviation > 5 else "ahead" if deviation < -3 else "on_track",
            })
        return out

    async def get_ship_trays(self) -> list[dict]:
        out = []
        for t in self.SHIP_TRAYS:
            readiness = round(t["ready"] / t["required"] * 100, 1)
            out.append({
                **t,
                "readiness_pct": readiness,
                "missing": t["required"] - t["ready"],
                "risk": "high" if readiness < 60 else "mid" if readiness < 80 else "low",
            })
        return out

    async def get_ship_workforce(self) -> list[dict]:
        out = []
        for w in self.SHIP_WORKFORCE:
            util = round(w["load_h"] / w["capacity_h"] * 100, 1)
            out.append({
                **w,
                "utilization": util,
                "surplus_h": w["capacity_h"] - w["load_h"],
                "status": "overload" if util > 100 else "tight" if util >= 90 else "ok",
            })
        return out

    async def get_ship_ecn(self) -> list[dict]:
        return [dict(e) for e in self.SHIP_ECN]

    async def what_if_reschedule(self, ecn_id: str, reassign_trade: str | None = None) -> dict:
        """What-if 排产推演：评估某 ECN 对关联船坞窗口的滑移影响（演示用确定性规则）。"""
        ecn = next((e for e in self.SHIP_ECN if e["ecn_id"] == ecn_id), None)
        if not ecn:
            return {"ok": False, "reason": "ecn_not_found"}
        # 关联船坞：找该船型所在船坞
        dock = next((d for d in self.SHIP_DOCKS if d["current_hull"] == ecn["hull"]
                     or d["next_hull"] == ecn["hull"]), self.SHIP_DOCKS[0])
        baseline_readiness = round(dock["current_progress"] * 0.6 + dock["next_tray_readiness"] * 0.4, 1)
        # ECN 直接增加 impact_days 滑移；若重新指派工种则缓解 40%
        slip = ecn["impact_days"]
        if reassign_trade:
            slip = round(slip * 0.6, 1)
        projected_readiness = round(max(0, baseline_readiness - slip * 1.5), 1)
        return {
            "ok": True,
            "ecn_id": ecn_id,
            "affected_hull": ecn["hull"],
            "affected_dock": dock["dock_id"],
            "baseline_window_readiness": baseline_readiness,
            "projected_window_readiness": projected_readiness,
            "readiness_drop": round(baseline_readiness - projected_readiness, 1),
            "reassign_trade": reassign_trade,
            "slip_days": slip,
        }
