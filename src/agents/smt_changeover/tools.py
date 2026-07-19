"""SMT换线Agent的工具集

数据优先来自 data/seed/smt_changeover.json，可切换真实MCP服务(MES/排程)。
"""

import json
from pathlib import Path



class SMTChangeoverTools:
    """SMT换线Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._line_config: dict = {}
        self._plans: dict = {}
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "smt_changeover.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._line_config = data.get("line_config", {})
                self._plans = data.get("changeover_plans", {})
                print(f"[SMTChangeoverTools] Loaded {len(self._plans)} changeover plans")
        except Exception as e:
            print(f"[SMTChangeoverTools] Seed load skipped: {e}")

    async def get_line_config(self, line_id: str) -> dict | None:
        """获取产线配置"""
        return self._line_config.get(line_id)

    async def get_changeover_plan(self, plan_key: str) -> dict | None:
        """获取换线计划"""
        return self._plans.get(plan_key)

    async def list_plan_keys(self) -> list[str]:
        """列出全部换线计划键"""
        return list(self._plans.keys())

    async def create_changeover_plan(self, plan_key: str, line_id: str) -> dict:
        """生成换线执行工单（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "workorder_id": f"CO-{line_id}",
            "plan_key": plan_key,
            "line_id": line_id,
        }
