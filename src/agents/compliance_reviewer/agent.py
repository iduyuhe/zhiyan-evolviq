"""合规闸门 Agent——研究案例范式合规审查（#399，2026-07-29 杜总定调）

🔴 把关三件事：
1. 匿名 / 真名双版边界：teaching_external 视图严禁含真实锚定公司名；
   teaching_internal 视图可含（real_anchor 仅此可见）。
2. 零真名泄漏复核：行业研究输出 / 案例库对外视图 / 企业入驻推荐 不得含
   真实锚定名片段（中兴 / 000063 / ZTE / zte）。
3. research_case 纪律校验：外圈 agent 在 research_case 模式不得写租户作用域记忆
   （atomic action 恒空），避免污染客户上下文。

本 Agent 自身输出亦零泄漏（仅回检查项 / 违规清单，不含任何真实锚定名）。
"""

import json
import logging

from src.agents.base import BaseAgent
# 🔴 零真名令牌单一真相源（2026-08-03 抽出到 src/common/leak.py，避免 im_bridge 牵动重型 agent import）
from src.common.leak import LEAK_TOKENS

logger = logging.getLogger(__name__)


class ComplianceReviewerAgent(BaseAgent):
    """合规闸门 Agent——研究案例范式合规审查"""

    name = "compliance_reviewer"
    description = "合规闸门：复核研究案例输出的匿名/真名边界 + 零真名泄漏 + research_case 纪律"

    async def analyze(self, goal: str, **kwargs) -> dict:
        checks: list[dict] = []
        violations: list[dict] = []

        # 1) 行业研究输出：零泄漏 + research_case 纪律
        from src.agents.industry_research.agent import industry_research_agent

        ir = await industry_research_agent.analyze("合规自检：通讯行业研究案例推演")
        checks.append(self._check_leak("industry_research", ir, violations))
        checks.append(self._check_research_case_discipline(ir, violations))

        # 1.5) 🆕 腿 B 首客 P3：半导体案例 + 试点管线（场景 A）零泄漏 + 纪律复核
        ir2 = await industry_research_agent.analyze(
            "合规自检：半导体行业研究案例推演（设备健康/能耗孪生试点）",
            case_id="case_semicon_2026",
        )
        checks.append(self._check_leak("industry_research(semicon)", ir2, violations))
        checks.append(self._check_research_case_discipline(ir2, violations))
        checks.append(self._check_pilot_ring_discipline(ir2, violations))

        # 2) 案例库教学双版边界
        from src.agents.case_curator.agent import case_curator_agent

        dual = await case_curator_agent.analyze("生成教学双版")
        checks.append(self._check_dual_version_boundary(dual, violations))

        # 3) 企业入驻推荐零泄漏（仅当 default 租户有画像时；无则跳过）
        from src.runtime.enterprise_store import profile_store

        if profile_store.get("default"):
            from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent

            ob = await enterprise_onboarding_agent.analyze("合规自检：入驻推荐", tenant_id="default")
            checks.append(self._check_leak("enterprise_onboarding", ob, violations))

        passed = len(violations) == 0
        return {
            "status": "completed",
            "passed": passed,
            "violation_count": len(violations),
            "checks": checks,
            "violations": violations,
            "summary": (
                "合规复核通过 ✅（匿名边界 / 零泄漏 / research_case 纪律均达标）"
                if passed
                else f"发现 {len(violations)} 处合规风险 ⚠️，须处置后重新复核"
            ),
        }

    # ---------- 检查项 ----------

    def _check_leak(self, who: str, result: dict, violations: list) -> dict:
        blob = json.dumps(result, ensure_ascii=False, default=str)
        hits = [t for t in LEAK_TOKENS if t in blob]
        ok = not hits
        if not ok:
            violations.append({
                "check": "zero_leak",
                "target": who,
                "detail": f"外发结果含真实锚定名片段 {hits}",
            })
        return {"check": "zero_leak", "target": who, "passed": ok}

    def _check_research_case_discipline(self, ir: dict, violations: list) -> dict:
        outer = ir.get("outer_ring", {})
        bad: list[str] = []
        for ag, r in outer.items():
            if not isinstance(r, dict):
                continue
            if r.get("mode") != "research_case":
                bad.append(f"{ag}:mode={r.get('mode')}")
            # research_case 下不写租户作用域记忆（atomic action 恒空）
            acts = r.get("actions_taken")
            if acts not in (None, [], ""):
                bad.append(f"{ag}:actions_taken 非空（污染租户上下文）")
        ok = not bad
        if not ok:
            violations.append({
                "check": "research_case_discipline",
                "target": "outer_ring",
                "detail": ";".join(bad),
            })
        return {"check": "research_case_discipline", "target": "outer_ring", "passed": ok}

    def _check_pilot_ring_discipline(self, ir: dict, violations: list) -> dict:
        """🆕 腿 B 首客 P3：试点管线（pilot_ring）research_case 纪律复核。

        场景 agent（pm_maintenance/energy_carbon）在 research_case 模式：
        actions_taken 恒空（不落工单/任务）+ mode 打标正确。
        """
        pilot = ir.get("pilot_ring", {})
        bad: list[str] = []
        if not pilot:
            bad.append("pilot_ring 缺失（试点场景未挂接）")
        for ag, r in pilot.items():
            if not isinstance(r, dict):
                continue
            if r.get("mode") != "research_case":
                bad.append(f"{ag}:mode={r.get('mode')}")
            acts = r.get("actions_taken")
            if acts not in (None, [], ""):
                bad.append(f"{ag}:actions_taken 非空（研究案例不得落工单/任务）")
        ok = not bad
        if not ok:
            violations.append({
                "check": "pilot_ring_discipline",
                "target": "pilot_ring",
                "detail": ";".join(bad),
            })
        return {"check": "pilot_ring_discipline", "target": "pilot_ring", "passed": ok}

    def _check_dual_version_boundary(self, dual: dict, violations: list) -> dict:
        bad: list[str] = []
        for d in dual.get("dual_versions", []):
            cid = d.get("teaching_external", {}).get("case_id", "?")
            ext = json.dumps(d.get("teaching_external", {}), ensure_ascii=False)
            for t in LEAK_TOKENS:
                if t in ext:
                    bad.append(f"{cid}:external 含真名 {t}")
            if not d.get("teaching_internal", {}).get("real_anchor"):
                bad.append(f"{cid}:internal 缺 real_anchor（双版不对称）")
        ok = not bad
        if not ok:
            violations.append({
                "check": "dual_version_boundary",
                "target": "case_curator",
                "detail": ";".join(bad),
            })
        return {"check": "dual_version_boundary", "target": "case_curator", "passed": ok}


compliance_reviewer_agent = ComplianceReviewerAgent()
