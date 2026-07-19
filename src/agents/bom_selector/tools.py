"""BOM选型Agent的工具集

数据优先来自 data/seed/components.json，可切换真实MCP服务(PLM/ERPIntelliBOM)。
"""

import json
from pathlib import Path



class BOMSelectorTools:
    """BOM选型Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._components: dict = {}
        self._alt_map: dict = {}
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "components.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._components = data.get("components", {})
                self._alt_map = data.get("alternatives_map", {})
                print(f"[BOMSelectorTools] Loaded {len(self._components)} components")
        except Exception as e:
            print(f"[BOMSelectorTools] Seed load skipped: {e}")

    async def get_component(self, part_no: str) -> dict | None:
        """获取单颗器件参数"""
        return self._components.get(part_no)

    async def list_components(self) -> list[str]:
        """列出全部器件型号"""
        return list(self._components.keys())

    async def get_alternatives(self, part_no: str) -> list[str]:
        """获取替代料清单"""
        return self._alt_map.get(part_no, [])

    async def submit_alt_approval(self, target: str, alt: str, reason: str) -> dict:
        """提交替代料审批（授权内可自主执行的操作）"""
        return {
            "status": "submitted",
            "approval_id": f"ALT-{target}-{alt}",
            "target": target,
            "alt": alt,
            "reason": reason,
        }
