"""行业研究 Agent——「研究案例」范式发动机（§3.7，2026-07-29 杜总定调）

范式突破：
- 不等签约客户，直接以区域行业标杆上市企业（公开数据可获取）为研究案例对象。
- 对外以「某某行业·某某公司」匿名呈现；内部锚定真实上市公司(real_anchor)做公开数据推演。
- 本 Agent 是范式发动机：拉取 CHANNEL_ENVIRONMENT 的 disclosure/benchmark/policy 信号 →
  建匿名"某某X公司"画像 → 调度 4 外圈 agent(research_case 模式)推演 → 对齐 real_anchor 出校准报告。

🔴 匿名铁律（沿用 disclosure_source）：输出 payload / status / summary 严禁含真实锚定公司名
（real_anchor 仅存内部变量，绝不进外发结果；前端/接口层须剥离 `calibration.anchor_internal`）。
"""

import logging

from src.agents.base import BaseAgent
from src.runtime.agent.router import execute_by_agent

logger = logging.getLogger(__name__)

# 🔴 内部锚定真实上市公司（杜总 2026-07-29 确认）；绝不进入外发 payload/status
REAL_ANCHOR = "中兴通讯（000063.SZ）"
ANON_LABEL = "某某通讯公司（研究案例·公开披露）"

# 外圈 4 agent：研究案例推演的接收方（与 disclosure_source 消费方一致）
OUTER_RING = ("executive_cockpit", "supply_chain", "compliance_q", "cost_analysis")


class IndustryResearchAgent(BaseAgent):
    """行业研究 Agent——研究案例范式发动机"""

    name = "industry_research"
    description = "研究案例范式发动机：选标杆→匿名画像→调度外圈4 agent推演→对齐真实锚定校准"

    def __init__(self):
        self.case_id = "case_telecom_2026"
        self.anon_label = ANON_LABEL
        # 🔴 真实锚定仅存内部变量，绝不进任何外发字段（结果 dict 中不得出现）
        self._real_anchor = REAL_ANCHOR
        # 研究案例真实锚定推演层（腿 A 实证：消费真实公开披露，非 mock 工厂数据）
        self._disclosure_facts = None
        self._derived_insights = []

    async def analyze(self, goal: str, case_id: str = None, **kwargs) -> dict:
        logger.info(f"[IndustryResearch] {goal[:60]}...")

        # 🔴 多案例支持（#398）：解析案例（指定 case_id 或案例库默认 active 案例）
        from src.agents.case_curator.agent import case_curator_agent

        case_curator_agent._ensure_seed()
        cid = case_id or case_curator_agent._active_case_id() or self.case_id
        case = case_curator_agent._get_case(cid)
        if case:
            self.case_id = cid
            self.anon_label = case.get("subject_anon", ANON_LABEL)
            industry = case.get("industry", "通讯设备 / 信息通信")
            # 🔴 真实锚定仅存内部变量，绝不进任何外发字段
            self._real_anchor = case.get("real_anchor") or REAL_ANCHOR
            # 腿 A 实证：从案例库加载真实公开披露与专家级研究结论
            self._disclosure_facts = case.get("disclosure_facts")
            self._derived_insights = case.get("derived_insights", [])
        else:
            industry = "通讯设备 / 信息通信"

        # 1) 拉取环境感知信号（disclosure / benchmark / policy）
        env = await self.env_context()
        signals = env.get("signals", [])
        disclosure = [s for s in signals if s.get("payload", {}).get("category") == "disclosure"]
        benchmark = [s for s in signals if s.get("payload", {}).get("category") == "benchmark"]
        policy = [s for s in signals if s.get("payload", {}).get("category") == "policy"]

        # 2) 建匿名画像（绝不写真实公司名）
        profile = self._build_anon_profile(disclosure, benchmark, policy, industry)

        # 3) 调度 4 外圈 agent(research_case 模式)——不污染租户上下文、不写租户作用域记忆
        outer = {}
        for ag in OUTER_RING:
            try:
                outer[ag] = await execute_by_agent(
                    ag, f"{self.anon_label}研究案例推演：{goal}",
                    mode="research_case", case_id=self.case_id,
                )
            except Exception as e:  # 单 agent 失败不破管
                logger.warning(f"⚠️ 外圈 {ag} 推演失败（不破管）：{e}")
                outer[ag] = {"status": "skipped", "error": str(e)}

        # 4) 对齐 real_anchor 校准（内部）——输出仍匿名
        calibration = self._calibrate(profile, outer)

        # 5) 汇总（严格净化，绝不外泄真实锚定名）
        return {
            "status": "completed",
            "mode": "research_case",
            "case_id": self.case_id,
            "subject_anon": self.anon_label,
            "summary": (
                f"研究案例推演完成（{self.anon_label}）：汇聚 {len(disclosure)} 条披露 / "
                f"{len(benchmark)} 条对标 / {len(policy)} 条政策信号，调度 4 外圈 agent 完成战略 / 供应链 / "
                f"合规 / 成本四维推演，形成匿名校准报告。"
            ),
            "anon_profile": profile,
            "outer_ring": {k: self._sanitize(v) for k, v in outer.items()},
            # 🔴 anchor_internal 为内部字段，前端/接口层必须剥离后再外发
            "calibration": calibration,
            "signals_used": {
                "disclosure": len(disclosure),
                "benchmark": len(benchmark),
                "policy": len(policy),
            },
            # 腿 A 实证：真实锚定推演层（消费真实公开披露，非 mock 工厂 KPI）
            "derived_insights": self._verify_insights(self._disclosure_facts, self._derived_insights),
            "disclosure_facts_ref": self._anon_facts_ref(self._disclosure_facts),
        }

    def _build_anon_profile(self, disclosure, benchmark, policy, industry: str = "通讯设备 / 信息通信") -> dict:
        return {
            "label": self.anon_label,
            "industry": industry,
            "disclosure_themes": [s.get("title") for s in disclosure[:5]],
            "benchmark_themes": [s.get("title") for s in benchmark[:5]],
            "policy_themes": [s.get("title") for s in policy[:5]],
        }

    def _calibrate(self, profile, outer) -> dict:
        """内部对齐真实锚定做校准说明。

        🔴 匿名铁律：返回结果中绝不出现真实锚定名（anchor_internal 仅作内部变量，
        用于推导 alignment_notes，但不得进入任何外发字段）。
        """
        notes = []
        if outer.get("executive_cockpit", {}).get("status") == "completed":
            notes.append("经营驾驶舱推演与公开披露营收 / 毛利主题基本自洽")
        if outer.get("supply_chain", {}).get("status") == "completed":
            notes.append("供应链推演与自研半导体器件降本主题可对应")
        if outer.get("compliance_q", {}).get("status") == "completed":
            notes.append("合规推演与全球市场准入风险主题可对应")
        if outer.get("cost_analysis", {}).get("status") == "completed":
            notes.append("成本推演与毛利结构改善主题可对应")
        # 腿 A 实证：真实锚定推演层已产出并经事实一致性自检的结论
        verified_list = self._verify_insights(self._disclosure_facts, self._derived_insights)
        verified = [i for i in verified_list if i.get("verified")]
        if verified:
            notes.append(f"真实锚定推演层产出 {len(verified)} 条经事实一致性自检的研究结论（消费真实公开披露）")
        base = 0.4 + 0.1 * len(notes)
        if verified:
            base = max(base, 0.5 + 0.1 * len(verified))
        return {
            "alignment_notes": notes,
            "confidence": round(min(base, 0.95), 2),
            "verified_insight_count": len(verified),
        }

    @staticmethod
    def _sanitize(result: dict) -> dict:
        """剥离任何可能外泄真实公司名的字段，并打标 research_case。"""
        if not isinstance(result, dict):
            return result
        result = dict(result)
        result.pop("real_anchor", None)
        result.pop("company", None)
        result["mode"] = "research_case"
        result.pop("agent", None)  # 防止与外层 agent 键冲突（外层统一由 router 补写）
        return result

    def _verify_insights(self, facts: dict, insights: list) -> list:
        """对每条研究结论做事实一致性自检：key_figures 是否都能在披露事实中找到依据。

        🔴 匿名铁律：仅基于案例内部 disclosure_facts 校验，不外泄真实锚定名。
        """
        if not insights:
            return []
        fact_blob = ""
        if facts:
            fact_blob = " ".join(
                f.get("metric", "") + " " + f.get("value", "") + " "
                + (f.get("yoy") or "") + " " + (f.get("share") or "")
                for f in facts.get("facts", [])
            )
        out = []
        for ins in insights:
            ins = dict(ins)
            missing = [k for k in ins.get("key_figures", []) if k not in fact_blob]
            ins["verified"] = len(missing) == 0
            ins["unverified_figures"] = missing
            out.append(ins)
        return out

    def _anon_facts_ref(self, facts: dict) -> dict | None:
        """外发仅给披露来源/年份/指标数摘要（绝不带可识别真名的细节）。"""
        if not facts:
            return None
        return {
            "source": facts.get("source"),
            "fiscal_year": facts.get("fiscal_year"),
            "fact_count": len(facts.get("facts", [])),
        }


industry_research_agent = IndustryResearchAgent()
