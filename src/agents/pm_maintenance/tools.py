"""设备预测维护Agent的工具集

每个工具是Agent可调用的能力——对应MCP协议中的一个tool。
数据优先来自 data/seed/pm_equipment.json，可切换到真实MCP服务（EAM/PLC）。
"""

import json
from pathlib import Path



class PMTools:
    """设备维护Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._equipments: list[dict] = []
        self._load_seed()

    def _load_seed(self):
        """从seed JSON加载设备档案"""
        try:
            seed_file = self._seed_dir / "pm_equipment.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._equipments = data.get("equipments", [])
                print(f"[PMTools] Loaded {len(self._equipments)} equipment profiles")
        except Exception as e:
            print(f"[PMTools] Seed load skipped: {e}")

    async def get_equipment_list(self) -> list[dict]:
        """获取全部设备清单"""
        return self._equipments

    async def get_equipment_health(self, equipment_id: str) -> dict | None:
        """获取单台设备健康档案"""
        for eq in self._equipments:
            if eq["equipment_id"] == equipment_id:
                return eq
        return None

    async def get_sensor_readings(self, equipment_id: str) -> dict:
        """获取设备实时传感器读数"""
        eq = await self.get_equipment_health(equipment_id)
        return eq.get("sensors", {}) if eq else {}

    async def get_parts_life(self, equipment_id: str) -> list[dict]:
        """获取设备关键部件寿命数据"""
        eq = await self.get_equipment_health(equipment_id)
        return eq.get("key_parts", []) if eq else []

    async def create_pm_workorder(self, equipment_id: str, parts: list[str], reason: str) -> dict:
        """创建预防维护工单（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "workorder_id": f"WO-PM-{equipment_id}",
            "equipment_id": equipment_id,
            "parts": parts,
            "reason": reason,
        }

    async def create_spare_part_order(self, part_no: str, qty: int, lead_days: int) -> dict:
        """创建备件采购申请"""
        return {"status": "requested", "part_no": part_no, "qty": qty, "lead_days": lead_days}
