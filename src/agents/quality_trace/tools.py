"""质量追溯Agent的工具集

数据优先来自 data/seed/quality_trace.json，可切换到真实MCP服务(MES/LIMS/设备日志)。
"""

import json
from pathlib import Path



class QualityTraceTools:
    """质量追溯Agent的工具集——真实种子数据 + MCP回退"""

    def __init__(self):
        self._seed_dir = Path(__file__).parents[3] / "data" / "seed"
        self._cases: list[dict] = []
        self._load_seed()

    def _load_seed(self):
        try:
            seed_file = self._seed_dir / "quality_trace.json"
            if seed_file.exists():
                with open(seed_file, encoding="utf-8") as f:
                    data = json.load(f)
                self._cases = data.get("cases", [])
                print(f"[QualityTraceTools] Loaded {len(self._cases)} trace cases")
        except Exception as e:
            print(f"[QualityTraceTools] Seed load skipped: {e}")

    async def get_case_list(self) -> list[dict]:
        """获取全部历史追溯案例摘要"""
        return [
            {
                "id": c["id"],
                "product": c["product"],
                "issue": c["issue"],
                "severity": c["severity"],
                "affected_qty": c["affected_qty"],
            }
            for c in self._cases
        ]

    async def get_case(self, case_id: str) -> dict | None:
        """按ID获取单条追溯案例"""
        for c in self._cases:
            if c["id"] == case_id:
                return c
        return None

    async def search_cases(self, query: str) -> dict | None:
        """根据缺陷关键词匹配历史案例（双向子串匹配，可复现，无随机）"""
        q = query.lower()
        for c in self._cases:
            issue = c["issue"].lower()
            issue_words = issue.split()
            # 查询是问题串的子串，或问题串是查询的子串，或任一分词命中
            if q in issue or issue in q or any(w in q for w in issue_words):
                return c
        return None

    async def create_capa(self, case_id: str, actions: list[str]) -> dict:
        """生成纠正预防措施(CAPA)任务（授权内可自主执行的操作）"""
        return {
            "status": "created",
            "task_id": f"CAPA-{case_id}",
            "case_id": case_id,
            "actions": actions,
        }

    async def open_investigation_ticket(self, query: str) -> dict:
        """未匹配历史案例时，开新追溯工单"""
        return {
            "status": "opened",
            "ticket_id": f"INV-{abs(hash(query)) % 100000:05d}",
            "query": query,
        }
