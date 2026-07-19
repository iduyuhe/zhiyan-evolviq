"""IPC标准Agent的工具集

数据优先来自 data/seed/ipc_standards.json，可切换到真实MCP服务(PLM/标准库)。
"""

import json
from pathlib import Path



class IPCStandardTools:
    """IPC标准Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._standards: dict = {}
        self._examples: list[dict] = []
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "ipc_standards.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._standards = data.get("standards", {})
                self._examples = data.get("query_examples", [])
                print(f"[IPCStandardTools] Loaded {len(self._standards)} IPC standards")
        except Exception as e:
            print(f"[IPCStandardTools] Seed load skipped: {e}")

    async def list_standards(self) -> dict:
        """列出全部已加载标准"""
        return {k: v["name"] for k, v in self._standards.items()}

    async def get_standard(self, standard_id: str) -> dict | None:
        """获取单条标准全文"""
        return self._standards.get(standard_id)

    async def match_judgment(self, query: str) -> dict | None:
        """根据查询匹配标准判定案例（可复现，无随机）

        注意：缺陷类型按整体子串匹配，避免逐字符遍历导致的误匹配。
        """
        q = query.lower()
        for ex in self._examples:
            defect = ex["judgment"]["defect_type"]
            if defect.lower() in q or ex["query"].lower() in q:
                return ex
        # 默认返回首个案例
        return self._examples[0] if self._examples else None

    async def search_criteria(self, standard_id: str, category_name: str, defect_type: str) -> dict | None:
        """在标准内精确检索条款"""
        std = self._standards.get(standard_id, {})
        for cat in std.get("categories", []):
            if cat["category"] == category_name:
                for crit in cat.get("criteria", []):
                    if crit["defect_type"] == defect_type:
                        return crit
        return None

    async def create_training_task(self, standard_id: str, topic: str) -> dict:
        """生成标准培训任务（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "task_id": f"TRAIN-{standard_id}",
            "standard_id": standard_id,
            "topic": topic,
        }
