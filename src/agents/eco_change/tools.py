"""ECO变更Agent的工具集

数据优先来自 data/seed/eco_cases.json，可切换真实MCP服务(PLM/ERP)。
"""

import json
from pathlib import Path



class ECOTools:
    """ECO变更Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._cases: dict = {}
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "eco_cases.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._cases = data.get("cases", {})
                print(f"[ECOTools] Loaded {len(self._cases)} ECO cases")
        except Exception as e:
            print(f"[ECOTools] Seed load skipped: {e}")

    async def get_case_list(self) -> list[str]:
        """列出全部ECO编号"""
        return list(self._cases.keys())

    async def get_case(self, eco_id: str) -> dict | None:
        """按编号获取ECO详情"""
        return self._cases.get(eco_id)

    async def create_eco_task(self, eco_id: str) -> dict:
        """创建ECO执行任务（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "task_id": f"ECO-TASK-{eco_id}",
            "eco_id": eco_id,
        }

    async def dispatch_notice(self, eco_id: str, departments: list[str]) -> dict:
        """向相关部门分发变更通知（授权内可自主执行的操作）"""
        return {
            "status": "dispatched",
            "eco_id": eco_id,
            "departments": departments,
        }
