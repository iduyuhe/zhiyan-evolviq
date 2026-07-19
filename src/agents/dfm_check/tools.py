"""DFM检查Agent的工具集

数据优先来自 data/seed/dfm_check.json，可切换真实MCP服务(ECAD/DFM引擎)。
"""

import json
from pathlib import Path



class DFMTools:
    """DFM检查Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._rules: dict = {}
        self._checks: list[dict] = []
        self._design_file = "PCB_REV2.3.gbr"
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "dfm_check.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._rules = data.get("rules", {})
                self._checks = data.get("design_checks", [])
                self._design_file = data.get("design_file", self._design_file)
                print(f"[DFMTools] Loaded {len(self._checks)} DFM checks, {len(self._rules)} rules")
        except Exception as e:
            print(f"[DFMTools] Seed load skipped: {e}")

    async def get_rules(self) -> dict:
        """获取DFM规则库"""
        return self._rules

    async def get_design_checks(self) -> list[dict]:
        """获取设计检查结果"""
        return self._checks

    async def get_design_file(self) -> str:
        """获取当前设计文件名"""
        return self._design_file

    async def create_dfm_report(self, design_file: str, grade: str) -> dict:
        """生成DFM评审报告（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "report_id": f"DFM-{design_file}",
            "design_file": design_file,
            "grade": grade,
        }

    async def open_design_review(self, rule_id: str, location: str) -> dict:
        """针对critical项发起设计评审（授权内可自主执行的操作）"""
        return {
            "status": "opened",
            "review_id": f"DR-{rule_id}",
            "rule_id": rule_id,
            "location": location,
        }
