"""OEE优化Agent的工具集

数据优先来自 data/seed/oee_lines.json，可切换真实MCP服务(MES/Andon)。
"""

import json
from pathlib import Path



class OEETools:
    """OEE优化Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._lines: dict = {}
        self._targets: dict = {}
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "oee_lines.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._lines = data.get("lines", {})
                self._targets = data.get("targets", {})
                print(f"[OEETools] Loaded {len(self._lines)} production lines")
        except Exception as e:
            print(f"[OEETools] Seed load skipped: {e}")

    async def get_line_list(self) -> list[dict]:
        """获取全部产线OEE概况（注入line_id）"""
        return [{"line_id": k, **v} for k, v in self._lines.items()]

    async def get_line(self, line_id: str) -> dict | None:
        """获取单条产线数据"""
        line = self._lines.get(line_id)
        return {"line_id": line_id, **line} if line else None

    async def get_targets(self) -> dict:
        """获取OEE目标值"""
        return self._targets

    async def create_improvement_task(self, line_id: str, focus: str) -> dict:
        """创建OEE改善任务（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "task_id": f"KAIZEN-{line_id}",
            "line_id": line_id,
            "focus": focus,
        }
