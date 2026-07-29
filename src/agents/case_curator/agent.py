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
        "disclosure_facts": {
            "source": "2025 年年度报告（2026-03-06 披露；公司官网 / 上证报 / 证券日报交叉核对）",
            "fiscal_year": 2025,
            "facts": [
                {"metric": "营业总收入", "value": "1339.0 亿元", "yoy": "+10.4%"},
                {"metric": "归母净利润", "value": "56.2 亿元", "yoy": "-33.32%（高基数+结构因素，非经营恶化）"},
                {"metric": "扣非归母净利润", "value": "33.7 亿元", "yoy": "—"},
                {"metric": "研发费用", "value": "227.6 亿元", "yoy": "占营收 17.0%"},
                {"metric": "现金分红比例", "value": "占归母净利润 35%", "yoy": "—"},
                {"metric": "运营商网络营收", "value": "628.6 亿元", "yoy": "-10.62%（国内承压）", "share": "46.9%"},
                {"metric": "政企业务营收", "value": "372.2 亿元", "yoy": "+100.5%（翻番，增长引擎）", "share": "27.8%"},
                {"metric": "消费者业务营收", "value": "338.2 亿元", "yoy": "+4.4%", "share": "25.26%"},
                {"metric": "算力业务营收", "value": "同比 +150%", "yoy": "占整体 24.6%"},
                {"metric": "服务器及存储营收", "value": "同比 +200%+", "yoy": "—"},
                {"metric": "数据中心产品营收", "value": "同比 +50%", "yoy": "—"},
                {"metric": "国内营收", "value": "897.4 亿元", "yoy": "+9.4%", "share": "67.0%"},
                {"metric": "国际营收", "value": "441.6 亿元", "yoy": "+12.4%", "share": "33.0%"},
                {"metric": "毛利率", "value": "阶段性承压", "yoy": "行业周期切换+业务结构变化"},
                {"metric": "战略主轴", "value": "连接+算力 双轮驱动 / AI 全栈", "yoy": "—"},
                {"metric": "全球地位", "value": "5G 基站/核心网/固网 全球第二；FWA&MBB 份额全球第一；PON CPE 发货全球第一", "yoy": "—"},
                {"metric": "智算落地", "value": "全球 500+ 绿色数据中心、万卡级智算中心；智算服务器进入互联网/电信/金融/电力头部核心场景", "yoy": "—"},
            ],
        },
        "derived_insights": [
            {
                "dimension": "strategy",
                "claim": "算力业务已成第二增长引擎，增长结构从运营商单一驱动转向'运营商基本盘 + 政企/算力新引擎'双轮。",
                "rationale": "算力营收同比 +150%、占整体 24.6%；政企业务（算力主力）同比 +100.5% 翻番成为整体增长引擎；与'连接+算力'双轮驱动战略自洽。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["同比 +150%", "占整体 24.6%", "+100.5%"],
            },
            {
                "dimension": "strategy",
                "claim": "表观净利下滑主要为基数与结构因素，盈利质量未恶化，经营韧性增强。",
                "rationale": "归母 56.2 亿同比 -33.32% 主因上年一次性收益高基数 + 毛利率阶段性承压；但营收重回增长 +10.4%、扣非 33.7 亿、研发占比 17% 高强度，非基本面恶化。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["-33.32%", "+10.4%", "17.0%"],
            },
            {
                "dimension": "supply_chain",
                "claim": "自研芯片 + 韧性供应链是算力 TCO 优势核心壁垒，对抗价格竞争加剧。",
                "rationale": "年报强调整合芯片/算法/架构/交付/标准五大能力，纵向自研是毛利率承压下维持 TCO 最优的关键护城河。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["17.0%", "阶段性承压"],
            },
            {
                "dimension": "supply_chain",
                "claim": "运营商国内承压倒逼供应链需求向政企与海外'大国大T'迁移，需调整产能与采购布局。",
                "rationale": "运营商国内受通信基础设施投资下降影响营收 -10.62%；国际 +12.4%、政企 +100.5%，供应链客户结构随之迁移。",
                "assertion_type": "descriptive",
                "value_judgment": "medium",
                "key_figures": ["-10.62%", "+12.4%", "+100.5%"],
            },
            {
                "dimension": "compliance",
                "claim": "全球市场准入与地缘贸易合规是核心持续性风险面。",
                "rationale": "国际占 33%、坚定'大国大T'战略与全球交付；出海依赖全球市场准入，出口管制与地缘合规为持续性风险。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["33.0%"],
            },
            {
                "dimension": "cost",
                "claim": "毛利率阶段性承压源于业务结构切换，非成本失控；降本应聚焦算力供应链 TCO 与政企交付效率。",
                "rationale": "毛利率承压来自行业周期 + 算力/政企占比上升的结构性现象；成本改善方向应为算力供应链协同与交付效率，而非一刀切压制造本。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["阶段性承压", "占整体 24.6%"],
            },
        ],
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
        # 🔴 多案例：若 goal 明确带 case_id，直接返回该案例详情
        import re

        m = re.search(r"case_[a-z0-9_]+", goal)
        if m:
            c = self._get_case(m.group(0))
            if c:
                return self._case_detail(c)
        # 搜索 / 查找（按 case_id / 匿名主题 / 行业 / 教学笔记模糊匹配）
        if "搜索" in goal or "search" in g or "查找" in goal or "查询" in goal or "找" in goal:
            return self._search_cases(goal)
        if "教学" in goal or "双版" in goal or "teaching" in g:
            return self._teaching_dual_version()
        if "推荐接口" in goal or "recommended" in g or "接口" in goal:
            return self._recommended_interfaces()
        # 默认：列出 / 汇总案例库
        return self._list_cases()

    # ---------- 多案例能力（#398） ----------

    def _get_case(self, case_id: str) -> dict | None:
        for c in self._load():
            if c["case_id"] == case_id:
                return c
        return None

    def _active_case_id(self) -> str | None:
        """默认案例：第一个 active 案例（先有后优，单案例时即它）。"""
        for c in self._load():
            if c.get("status", "active") == "active":
                return c["case_id"]
        cases = self._load()
        return cases[0]["case_id"] if cases else None

    def _search_cases(self, query: str) -> dict:
        import re

        q = query.lower().replace("搜索", "").replace("查找", "").replace("查询", "").replace("找", "").strip()
        if not q:
            return self._list_cases()
        # 分词：英文/数字连续段整体保留；中文按 2 字滑动窗口生成词素，任一命中即匹配
        raw_tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", q)
        tokens: list[str] = []
        for t in raw_tokens:
            if re.search(r"[A-Za-z0-9]", t):
                if len(t) >= 2:
                    tokens.append(t)
            else:
                for i in range(len(t) - 1):
                    tokens.append(t[i : i + 2])
        if not tokens:
            tokens = [q]
        out = []
        for c in self._load():
            hay = " ".join([
                c.get("case_id", ""), c.get("subject_anon", ""),
                c.get("industry", ""), c.get("real_anchor", ""),
                c.get("teaching_notes_anon", ""),
            ]).lower()
            if any(t.lower() in hay for t in tokens):
                out.append(c)
        return {
            "status": "completed",
            "query": q,
            "tokens": tokens,
            "match_count": len(out),
            "cases": [
                {
                    "case_id": c["case_id"],
                    "subject_anon": c["subject_anon"],
                    "industry": c["industry"],
                    "status": c.get("status", "active"),
                }
                for c in out
            ],
            "summary": f"搜索「{q}」命中 {len(out)} 个案例" if out else f"搜索「{q}」无匹配案例",
        }

    def _case_detail(self, c: dict) -> dict:
        """单案例详情（对外匿名视图，绝不带 real_anchor）。"""
        return {
            "status": "completed",
            "case": {
                "case_id": c["case_id"],
                "subject_anon": c["subject_anon"],
                "industry": c["industry"],
                "recommended_interfaces": c.get("recommended_interfaces", []),
                "teaching_notes_anon": c.get("teaching_notes_anon", ""),
                "status": c.get("status", "active"),
                "updated_at": c.get("updated_at", ""),
            },
            "summary": f"案例 {c['case_id']} 详情（{c['subject_anon']}）",
        }

    def _list_cases(self) -> dict:
        cases = self._load()
        return {
            "status": "completed",
            "case_count": len(cases),
            "active_case_id": self._active_case_id(),
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
