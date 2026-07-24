"""能源碳 ESG Agent 工具层——能耗监控、碳排放/碳足迹核算、节能机会（确定性种子数据）

数据层：内置各产线电表与排放因子种子，可切换真实能源管理系统(EMS)/碳平台。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""


class EnergyCarbonTools:
    """能源碳工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 各产线能耗种子（kWh/周）；green_ratio=绿电占比
    LINES = [
        {"line_id": "SMT-L01", "name": "SMT 产线1", "energy_kwh": 48000, "green_ratio": 30.0, "output_units": 52000},
        {"line_id": "SMT-L02", "name": "SMT 产线2", "energy_kwh": 52000, "green_ratio": 18.0, "output_units": 54000},
        {"line_id": "ASSY", "name": "组装测试线", "energy_kwh": 22000, "green_ratio": 25.0, "output_units": 41000},
        {"line_id": "DIFF", "name": "扩散/炉管区", "energy_kwh": 60000, "green_ratio": 8.0, "output_units": 30000},
    ]

    # 排放因子：电网 0.581 tCO2/MWh（中国区域电网均值）；绿电近似 0
    GRID_FACTOR = 0.581  # tCO2 / MWh
    # 单位产值碳强度目标（tCO2 / 万元产值）
    TARGET_INTENSITY = 0.45

    # 节能/降碳机会库（确定性）
    OPPORTUNITIES = [
        {"measure": "空压机系统能效改造", "saving_kwh": 18000, "payback_yr": 1.8, "cost_wan": 65},
        {"measure": "绿电采购比例提升至 35%", "saving_co2_t": 42.0, "payback_yr": 2.5, "cost_wan": 90},
        {"measure": "回流焊余热回收", "saving_kwh": 9500, "payback_yr": 2.1, "cost_wan": 38},
        {"measure": "LED+分区照明智控", "saving_kwh": 4200, "payback_yr": 1.2, "cost_wan": 12},
    ]

    async def get_energy_list(self) -> list[dict]:
        out = []
        for ln in self.LINES:
            carbon_t = ln["energy_kwh"] / 1000 * self.GRID_FACTOR * (1 - ln["green_ratio"] / 100)
            out.append({
                "line_id": ln["line_id"],
                "name": ln["name"],
                "energy_kwh": ln["energy_kwh"],
                "green_ratio": ln["green_ratio"],
                "carbon_t": round(carbon_t, 1),
                "status": "critical" if ln["green_ratio"] < 15 else "warning" if ln["green_ratio"] < 25 else "good",
            })
        return out

    async def get_carbon_summary(self) -> dict:
        lines = await self.get_energy_list()
        total_kwh = sum(l["energy_kwh"] for l in lines)
        total_carbon = round(sum(l["carbon_t"] for l in lines), 1)
        total_green = sum(l["energy_kwh"] * l["green_ratio"] / 100 for l in lines)
        green_ratio = round(total_green / total_kwh * 100, 1)
        # 碳强度：以总产值（万元）近似=各线产出/1000 估算，简化用总能耗折算
        # 这里用"吨CO2 / 万片产出"作为可对标强度指标
        total_output = sum(l["output_units"] for l in self.LINES)
        intensity_per_10k = round(total_carbon / (total_output / 10000), 3)
        return {
            "total_energy_kwh": total_kwh,
            "total_carbon_t": total_carbon,
            "green_ratio": green_ratio,
            "intensity_per_10k": intensity_per_10k,
            "target_intensity": self.TARGET_INTENSITY,
        }

    async def create_saving_task(self, measure: str) -> dict:
        return {"task_id": f"ES-{measure[:6]}", "measure": measure, "note": "已生成节能降碳改善任务"}
