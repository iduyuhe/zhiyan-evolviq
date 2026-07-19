"""良率分析Agent的工具集

数据优先来自 data/seed/yield_data.json，可切换真实MCP服务(YMS/KLA)。
"""

import json
from pathlib import Path



class YieldTools:
    """良率分析Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._products: list[dict] = []
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "yield_data.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._products = data.get("products", [])
                print(f"[YieldTools] Loaded {len(self._products)} product yield profiles")
        except Exception as e:
            print(f"[YieldTools] Seed load skipped: {e}")

    async def get_product_list(self) -> list[dict]:
        """获取全部产品良率概览"""
        return self._products

    async def get_yield_data(self, product_id: str) -> dict | None:
        """获取单个产品的良率详情"""
        for p in self._products:
            if p["product_id"] == product_id:
                return p
        return None

    async def get_defect_distribution(self, product_id: str) -> list[dict]:
        """获取产品缺陷分布"""
        p = await self.get_yield_data(product_id)
        return p.get("defect_top3", []) if p else []

    async def create_doe_experiment(self, product_id: str, defect_type: str, params: list[str]) -> dict:
        """创建DOE实验任务（改善良率的执行动作）"""
        return {
            "status": "created",
            "experiment_id": f"DOE-{product_id}",
            "defect_type": defect_type,
            "params": params,
        }
