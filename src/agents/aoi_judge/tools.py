"""AOI判定Agent的工具集

数据优先来自 data/seed/aoi_results.json，可切换真实MCP服务(AOI/SPC)。
"""

import json
from pathlib import Path



class AOITools:
    """AOI判定Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._results: dict = {}
        self._optim_factor = 0.35
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "aoi_results.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._results = data.get("results", {})
                self._optim_factor = data.get("optimization_factor", 0.35)
                print(f"[AOITools] Loaded AOI results for {len(self._results)} lines")
        except Exception as e:
            print(f"[AOITools] Seed load skipped: {e}")

    async def get_line_result(self, line_id: str) -> dict | None:
        """获取产线AOI检测结果"""
        return self._results.get(line_id)

    async def list_line_ids(self) -> list[str]:
        """列出有数据的产线"""
        return list(self._results.keys())

    async def create_threshold_optimization(self, line_id: str, suggestions: list[str]) -> dict:
        """生成AOI阈值优化任务（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "task_id": f"AOI-OPT-{line_id}",
            "line_id": line_id,
            "suggestions": suggestions,
        }
