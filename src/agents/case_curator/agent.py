"""案例库策展 Agent——拥有案例库活体本体（§3.7，2026-07-29 杜总定调）

案例库是产品活体本体、行业分析资产、教学素材、获客内容引擎。
本 Agent 负责案例库版本化、推荐接口挂载、教学双版生成（对外匿名 / 对内真名）。

🔴 匿名铁律：对外输出(teaching_external 视图)严禁含真实锚定公司名；
real_anchor 仅存案例内部字段，进入 teaching_internal 视图，绝不进 teaching_external。
"""

import json
import logging
import os

from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)

CASE_STORE_PATH = os.path.join(os.path.dirname(__file__), "cases.json")

# 🔴 单案例种子（杜总 2026-07-29 确认仅做 1 行业 1 公司：通讯·中兴通讯）
# real_anchor 仅内部可见；subject_anon 对外呈现。
DEFAULT_CASES = [
    {
        "case_id": "case_telecom_2026",
        "subject_anon": "某某通讯公司（研究案例·公开披露）",
        "industry": "通讯设备 / 信息通信",
        "real_anchor": "中兴通讯（000063.SZ）",  # 🔴 内部锚定真实上市公司，仅 internal 视图
        "recommended_interfaces": [
            "industry_research",
            "executive_cockpit",
            "supply_chain",
            "compliance_q",
            "cost_analysis",
        ],
        "teaching_notes_anon": (
            "对外以匿名案例呈现，演示「研究案例范式」如何在通讯行业标杆企业推演 "
            "战略 / 供应链 / 合规 / 成本四维，并对外匿名、对内真名双版教学。"
        ),
        "teaching_notes_internal": (
            "内部锚定中兴通讯(000063.SZ)公开披露，用于校准行业研究推演；"
            "真实公司名仅在本视图出现，对外一律匿名。"
        ),
        "status": "active",
        "updated_at": "2026-07-29",
    }
]


class CaseCuratorAgent(BaseAgent):
    """案例库策展 Agent"""

    name = "case_curator"
    description = "案例库策展：列/汇总案例、挂推荐接口、生成教学双版(对外匿名/对内真名)"

    def __init__(self):
        self.store_path = CASE_STORE_PATH

    def _load(self) -> list:
        try:
            if os.path.exists(self.store_path):
                with open(self.store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save(self, cases: list):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)

    def _ensure_seed(self):
        """案例库为空时写入单案例种子（先有后优，只做 1 行业 1 公司）。"""
        cases = self._load()
        if not cases:
            self._save(DEFAULT_CASES)

    async def analyze(self, goal: str) -> dict:
        self._ensure_seed()
        g = goal.lower()
        if "教学" in goal or "双版" in goal or "teaching" in g:
            return self._teaching_dual_version()
        if "推荐接口" in goal or "recommended" in g or "接口" in goal:
            return self._recommended_interfaces()
        # 默认：列出 / 汇总案例库
        return self._list_cases()

    def _list_cases(self) -> dict:
        cases = self._load()
        return {
            "status": "completed",
            "case_count": len(cases),
            "cases": [
                {
                    "case_id": c["case_id"],
                    "subject_anon": c["subject_anon"],
                    "industry": c["industry"],
                    "status": c.get("status", "active"),
                    "updated_at": c.get("updated_at", ""),
                }
                for c in cases
            ],
            "summary": f"案例库共 {len(cases)} 个研究案例（均对外匿名）",
        }

    def _recommended_interfaces(self) -> dict:
        cases = self._load()
        out = [
            {
                "case_id": c["case_id"],
                "subject_anon": c["subject_anon"],
                "recommended_interfaces": c.get("recommended_interfaces", []),
            }
            for c in cases
        ]
        return {
            "status": "completed",
            "cases": out,
            "summary": f"已为 {len(cases)} 个案例挂载推荐接口",
        }

    def _teaching_dual_version(self) -> dict:
        """生成教学双版：对外匿名 / 对内真名（real_anchor 不进 external 视图）。"""
        cases = self._load()
        dual = []
        for c in cases:
            external = {
                "case_id": c["case_id"],
                "subject_anon": c["subject_anon"],
                "industry": c["industry"],
                "teaching_notes": c.get("teaching_notes_anon", ""),
            }
            internal = {
                "case_id": c["case_id"],
                "real_anchor": c.get("real_anchor"),  # 🔴 仅内部视图含真名
                "subject_anon": c["subject_anon"],
                "industry": c["industry"],
                "teaching_notes": c.get("teaching_notes_internal", ""),
            }
            dual.append({"teaching_external": external, "teaching_internal": internal})
        return {
            "status": "completed",
            "dual_version_count": len(dual),
            "dual_versions": dual,
            "summary": f"生成 {len(dual)} 个案例的教学双版（外部匿名 / 内部真名）",
        }


case_curator_agent = CaseCuratorAgent()
