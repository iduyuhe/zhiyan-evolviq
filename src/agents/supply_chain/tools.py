"""供应链Agent的MCP工具集

每个工具是Agent可调用的能力——对应MCP协议中的一个tool。
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path



@dataclass
class SupplyCheckResult:
    """齐套检查结果"""
    material_code: str
    material_name: str
    required_qty: int
    available_qty: int
    shortage_qty: int
    risk_level: str  # low / medium / high / critical
    alternative: str | None = None


class SupplyChainTools:
    """供应链Agent的工具集"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._seed_loaded = False
        self._seed_bom: dict | None = None
        self._seed_inv: dict = {}
        self._seed_po: dict = {}
        self._load_seed()

    def _load_seed(self):
        """从seed JSON文件加载数据（优先加载SMIC数据）"""
        try:
            # 优先使用SMIC数据（如果存在）
            smic_bom = self._seed_dir / "smic_bom.json"
            smic_inv = self._seed_dir / "smic_inventory.json"
            smic_po = self._seed_dir / "smic_po.json"

            if smic_bom.exists() and smic_inv.exists():
                with open(smic_bom, encoding="utf-8") as f:
                    self._seed_bom = json.load(f)
                with open(smic_inv, encoding="utf-8") as f:
                    self._seed_inv = json.load(f)
                with open(smic_po, encoding="utf-8") as f:
                    po_list = json.load(f)
                    for po in po_list:
                        code = po["material_code"]
                        if code not in self._seed_po:
                            self._seed_po[code] = []
                        self._seed_po[code].append(po)
                self._seed_loaded = True
                print(f"[Tools] Loaded SMIC seed data: {len(self._seed_bom.get('items',[]))} items")
                return

            # 回退到通用种子数据
            bom_file = self._seed_dir / "bom_npi_007.json"
            inv_file = self._seed_dir / "inventory.json"
            po_file = self._seed_dir / "po_data.json"

            if bom_file.exists():
                with open(bom_file, encoding="utf-8") as f:
                    self._seed_bom = json.load(f)

            if inv_file.exists():
                with open(inv_file, encoding="utf-8") as f:
                    self._seed_inv = json.load(f)

            if po_file.exists():
                po_list = json.loads(po_file.read_text(encoding="utf-8"))
                for po in po_list:
                    code = po["material_code"]
                    if code not in self._seed_po:
                        self._seed_po[code] = []
                    self._seed_po[code].append(po)

            self._seed_loaded = bool(self._seed_bom)
            if self._seed_loaded:
                print(f"[Tools] Loaded seed data: {len(self._seed_bom.get('items',[]))} BOM items")
        except Exception as e:
            print(f"[Tools] Seed load skipped: {e}")

    async def get_bom_data(self, bom_id: str) -> dict:
        """获取BOM数据"""
        return self._mock_bom(bom_id)

    async def get_inventory(self, material_codes: list[str]) -> dict:
        """获取物料库存"""
        return self._mock_inventory(material_codes)

    async def get_po_data(self, material_codes: list[str]) -> dict:
        """获取采购订单数据"""
        return self._mock_po(material_codes)

    async def find_alternatives(self, material_code: str, max_price_variation_pct: float = 5.0) -> list[dict]:
        """查找替代料"""
        return self._mock_alternatives(material_code, max_price_variation_pct)

    async def lock_inventory(self, material_code: str, qty: int, session_id: str) -> dict:
        """锁定库存（授权内自主执行的操作）"""
        return {"status": "locked", "material_code": material_code, "qty": qty}

    async def create_purchase_suggestion(self, material_code: str, qty: int, reason: str) -> dict:
        """创建采购建议"""
        return {"status": "suggested", "material_code": material_code, "qty": qty}

    # --- Mock数据方法（MVP离线验证用）---

    def _mock_bom(self, bom_id: str) -> dict:
        """获取BOM数据（优先seed数据）"""
        if self._seed_bom:
            return {**self._seed_bom, "bom_id": bom_id}
        # 无seed数据，用硬编码备选
        return {
            "bom_id": bom_id,
            "product_name": "NPI-PCBA-007",
            "total_qty": 5000,
            "items": [
                {"material_code": "RES-001", "name": "贴片电阻 10KΩ", "qty": 10000, "ref": "R1-R20"},
                {"material_code": "CAP-001", "name": "贴片电容 100nF", "qty": 5000, "ref": "C1-C10"},
                {"material_code": "IC-001", "name": "主控芯片 STM32F4", "qty": 5000, "ref": "U1"},
                {"material_code": "CONN-001", "name": "排针 2x20", "qty": 5000, "ref": "J1"},
                {"material_code": "PCB-001", "name": "PCB板 4层", "qty": 5000, "ref": "PCB1"},
            ]
        }

    def _mock_inventory(self, material_codes: list[str]) -> dict:
        """获取库存数据（优先seed数据）"""
        if self._seed_inv:
            return {code: self._seed_inv.get(code, {"on_hand": 0, "reserved": 0}) for code in material_codes}
        # 备选硬编码
        data = {
            "RES-001": {"on_hand": 15000, "reserved": 2000, "warehouse": "A1"},
            "CAP-001": {"on_hand": 3000, "reserved": 500, "warehouse": "A1"},
            "IC-001": {"on_hand": 2000, "reserved": 0, "warehouse": "B2"},
            "CONN-001": {"on_hand": 8000, "reserved": 1000, "warehouse": "A3"},
            "PCB-001": {"on_hand": 0, "reserved": 0, "warehouse": "C1"},
        }
        return {code: data.get(code, {"on_hand": 0, "reserved": 0}) for code in material_codes}

    def _mock_po(self, material_codes: list[str]) -> dict:
        """获取PO数据（优先seed数据）"""
        if self._seed_po:
            return {code: self._seed_po.get(code, []) for code in material_codes}
        # 备选硬编码
        data = {
            "RES-001": [{"po": "PO-2026-001", "qty": 20000, "expected": "2026-07-20", "status": "in_transit"}],
            "CAP-001": [{"po": "PO-2026-002", "qty": 10000, "expected": "2026-07-25", "status": "confirmed"}],
            "IC-001": [{"po": "PO-2026-003", "qty": 5000, "expected": "2026-08-01", "status": "confirmed"}],
            "CONN-001": [{"po": "PO-2026-004", "qty": 5000, "expected": "2026-07-18", "status": "in_transit"}],
            "PCB-001": [{"po": "PO-2026-005", "qty": 5000, "expected": "2026-07-30", "status": "delayed"}],
        }
        return {code: data.get(code, []) for code in material_codes}

    def _mock_alternatives(self, material_code: str, max_price_variation_pct: float) -> list[dict]:
        """替代方案（优先SMIC半导体数据，带国产/进口标签）"""
        # 半导体物料替代
        semi_alts = {
            "SI-001": [  # 8英寸抛光硅片
                {"code": "SI-004", "name": "8英寸抛光硅片(II)", "price": 82.0, "supplier": "中环股份", "lead_time_days": 35, "rating": 4.3, "source": "domestic"},
                {"code": "SI-005", "name": "8英寸退火硅片", "price": 95.0, "supplier": "上海新傲", "lead_time_days": 28, "rating": 4.0, "source": "domestic"},
            ],
            "SI-002": [  # 12英寸抛光硅片
                {"code": "SI-006", "name": "12英寸抛光硅片", "price": 210.0, "supplier": "沪硅产业", "lead_time_days": 40, "rating": 4.2, "source": "domestic"},
                {"code": "SI-007", "name": "12英寸外延片", "price": 280.0, "supplier": "SUMCO Japan", "lead_time_days": 50, "rating": 4.8, "source": "imported"},
            ],
            "PR-001": [  # ArF光刻胶
                {"code": "PR-004", "name": "ArF光刻胶(国产)", "price": 2600.0, "supplier": "南大光电", "lead_time_days": 35, "rating": 3.8, "source": "domestic"},
                {"code": "PR-005", "name": "ArF光刻胶", "price": 3200.0, "supplier": "JSR Japan", "lead_time_days": 45, "rating": 4.9, "source": "imported"},
            ],
            "PR-002": [  # KrF光刻胶
                {"code": "PR-006", "name": "KrF光刻胶(国产)", "price": 1400.0, "supplier": "北京科华", "lead_time_days": 25, "rating": 4.0, "source": "domestic"},
                {"code": "PR-007", "name": "KrF光刻胶", "price": 1800.0, "supplier": "TOK Japan", "lead_time_days": 40, "rating": 4.7, "source": "imported"},
            ],
            "GAS-003": [  # NF3
                {"code": "GAS-005", "name": "三氟化氮 NF3(国产)", "price": 350.0, "supplier": "中船重工718所", "lead_time_days": 25, "rating": 4.3, "source": "domestic"},
            ],
            "GAS-004": [  # WF6
                {"code": "GAS-006", "name": "六氟化钨 WF6(国产)", "price": 480.0, "supplier": "华特气体", "lead_time_days": 25, "rating": 4.1, "source": "domestic"},
            ],
            "TGT-001": [  # Ti靶
                {"code": "TGT-004", "name": "钛靶 Ti(国产)", "price": 4200.0, "supplier": "有研新材", "lead_time_days": 35, "rating": 4.0, "source": "domestic"},
            ],
            "TGT-002": [  # Cu靶
                {"code": "TGT-005", "name": "铜靶 Cu(国产)", "price": 3000.0, "supplier": "江丰电子", "lead_time_days": 30, "rating": 4.2, "source": "domestic"},
                {"code": "TGT-006", "name": "铜靶 Cu", "price": 3800.0, "supplier": "Tosoh Japan", "lead_time_days": 60, "rating": 4.7, "source": "imported"},
            ],
            "CAP-001": [
                {"code": "CAP-002", "name": "贴片电容 100nF X7R", "price": 0.08, "supplier": "风华高科", "lead_time_days": 7, "rating": 4.5, "source": "domestic"},
                {"code": "CAP-003", "name": "贴片电容 100nF C0G", "price": 0.12, "supplier": "三星电机", "lead_time_days": 14, "rating": 4.8, "source": "imported"},
            ],
            "IC-001": [
                {"code": "IC-002", "name": "主控芯片 GD32F4", "price": 12.50, "supplier": "兆易创新", "lead_time_days": 10, "rating": 4.2, "source": "domestic"},
            ],
        }
        return semi_alts.get(material_code, [])
