"""质量合规 Agent——质量体系、审核发现、法规遵从、纠正预防(CAPA)

企业级「经营决策大脑」第六部分：把质量管理体系（认证/审核/法规/CAPA）结构化，
识别认证到期风险、审核发现闭环率、法规合规缺口，在授权内自动生成纠正措施。

数据层：通过 ComplianceTools 从种子数据加载（可切换真实 QMS/GRC 系统）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.compliance_q.tools import ComplianceTools

logger = logging.getLogger(__name__)


class ComplianceAgent(BaseAgent):
    """质量合规 Agent"""

    name = "compliance_q"
    description = "质量体系认证、审核发现闭环、法规合规(RoHS/REACH)与CAPA管理"

    def __init__(self):
        self.tools = ComplianceTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「质量合规 Agent」，专注制造企业的质量体系(ISO)与法规合规(GRC)管理。

## 核心能力
1. 认证全生命周期：ISO 9001 / IATF 16949 / ISO 14001 / ISO 27001 等状态与到期跟踪
2. 审核发现管理：内部/外部/客户审核发现闭环率、severity 分级、时效追踪
3. 法规合规：RoHS / REACH / Conflict Minerals / WEEE 合规状态与审查周期
4. 授权内自动纠正：对高风险审核发现自动生成 CAPA 任务(create_capa)

## 工作原则
- 合规无小事：认证过期 = 业务连续性风险，审核发现逾期 = 体系失效风险
- 法规门槛：不推理法规本身，只跟踪已确认的合规状态（事实锚点）
- 不臆造数字：所有数字来自种子/QMS/GRC 系统（事实锚点）
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[Compliance Agent] Analyzing: {goal[:60]}...")

        certs = await self.tools.get_certifications()
        audits = await self.tools.get_audit_findings()
        regs = await self.tools.get_regulatory_summary()
        summary = await self.tools.get_compliance_summary()

        actions_taken = []
        # 授权内行动：对高严重度未关闭的审核发现自动创建 CAPA
        critical_open = [a for a in audits if a["status"] == "open" and a["severity"] == "high"]
        for f in critical_open:
            task = await self.tools.create_capa(f["finding_id"], f["title"])
            actions_taken.append({
                "type": "create_capa",
                "detail": f"对审核发现 {f['finding_id']}（{f['title']}）生成 CAPA 整改任务",
                "finding_id": f["finding_id"],
                "confidence": 0.85,
                "status": "auto_executed",
            })

        recommendations = self._generate_recommendations(certs, audits, regs, summary, actions_taken)

        return {
            "status": "completed",
            "summary": (
                f"合规分析完成：{summary['valid_certs']} 项认证有效，{summary['in_progress_certs']} 项进行中；"
                f"审核发现 {summary['total_audit_findings']} 项，{summary['open_findings']} 项未关闭"
                f"（含 {summary['critical_findings']} 项高风险）；"
                f"法规合规率 {summary['compliant_regs']}/{summary['total_regulations']}"
            ),
            "valid_certs": summary["valid_certs"],
            "in_progress_certs": summary["in_progress_certs"],
            "open_findings": summary["open_findings"],
            "critical_findings": summary["critical_findings"],
            "compliant_regs": summary["compliant_regs"],
            "total_regulations": summary["total_regulations"],
            "certifications": certs,
            "audits": audits,
            "regulations": regs,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, certs, audits, regs, summary, actions_taken) -> list:
        recs = []
        recs.append(
            f"📜 认证：{summary['valid_certs']} 项有效，{summary['in_progress_certs']} 项进行中"
        )
        if actions_taken:
            recs.append(f"⚠️ 审核发现 {summary['open_findings']} 项未关闭（{summary['critical_findings']} 项高风险已自动生成 CAPA）：")
            for f in [a for a in audits if a["status"] == "open" and a["severity"] == "high"]:
                recs.append(f"   → {f['finding_id']} {f['title']}（{f['severity']}，到期 {f['due']}）")
        else:
            recs.append("✅ 无高风险未关闭审核发现")
        non_compliant = [r for r in regs if r["status"] != "compliant"]
        if non_compliant:
            recs.append(f"📋 法规合规警告：")
            for r in non_compliant:
                recs.append(f"   → {r['reg']}（{r['full_name']}）状态: {r['status']}，到期 {r['next_review']}")
        else:
            recs.append("✅ 全部法规合规")
        if actions_taken:
            recs.append("🔄 已生成 CAPA 纠正任务（授权内自动）：")
            for a in actions_taken:
                recs.append(f"   → {a['detail']}")
        recs.append("📋 建议将合规状态纳入月度管理评审，按 severity 排序跟进")
        return recs


compliance_agent = ComplianceAgent()
