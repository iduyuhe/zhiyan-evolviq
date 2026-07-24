"""研发新产导入 Agent——NPI 项目全生命周期、里程碑、批量试产

企业级「经营决策大脑」第八部分：把研发新品导入(NPI)项目管理结构化，
识别项目风险、里程碑延迟，在授权内自动生成加速推进建议。

数据层：通过 NpiTools 从种子数据加载（可切换真实 PLM/PMS 系统）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.rd_npi.tools import NpiTools

logger = logging.getLogger(__name__)


class NpiAgent(BaseAgent):
    """研发新产导入 Agent"""

    name = "rd_npi"
    description = "NPI 项目全生命周期管理、里程碑、批量试产与风险识别"

    def __init__(self):
        self.tools = NpiTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「研发新产导入 Agent」(NPI)，专注新产品从概念到量产的端到端管理。

## 核心能力
1. NPI 项目看板：各项目当前阶段(概念→设计→原型→小批量→量产)、进度与责任人
2. 里程碑跟踪：关键节点预期 vs 实际日期，识别延迟与风险
3. 授权内加速推进：对高风险/延后项目自动生成加速行动建议(expedite_project)

## 工作原则
- NPI 是收入引擎：准时量产 = 市场窗口，延迟=机会损失
- 风险前置：On_schedule=False 或 risk=high 即预警
- 不臆造数字：所有数字来自种子/PLM 系统（事实锚点）
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[NPI Agent] Analyzing: {goal[:60]}...")

        projects = await self.tools.get_npi_projects()
        high_risk = [p for p in projects if p["risk"] == "high" or not p["on_schedule"]]
        total_stages = set(p["stage"] for p in projects)

        actions_taken = []
        # 授权内行动：对高风险/延后项目生成加速推进建议
        for p in high_risk:
            reason = p.get("risk_note", f"进度延后（里程碑{p['milestone_pct']}%）")
            task = await self.tools.expedite_project(p["id"], reason)
            actions_taken.append({
                "type": "expedite_project",
                "detail": f"为 {p['name']}（{reason}）生成加速推进行动项",
                "project_id": p["id"],
                "confidence": 0.83,
                "status": "auto_executed",
            })

        recommendations = self._generate_recommendations(projects, high_risk, actions_taken)

        return {
            "status": "completed",
            "summary": (
                f"NPI 分析完成：共 {len(projects)} 个项目，覆盖 {len(total_stages)} 个阶段；"
                f"{len(high_risk)} 个项目存在风险，已自动生成加速建议"
            ),
            "total_projects": len(projects),
            "stage_coverage": len(total_stages),
            "high_risk_count": len(high_risk),
            "on_schedule_count": sum(1 for p in projects if p["on_schedule"]),
            "projects": projects,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, projects, high_risk, actions_taken) -> list:
        recs = []
        on_sch = [p for p in projects if p["on_schedule"]]
        recs.append(f"🔬 共 {len(projects)} 个 NPI 项目：{len(on_sch)} 个按时，{len(high_risk)} 个存在风险")
        for p in projects:
            status_icon = "✅" if p["on_schedule"] else "⚠️"
            recs.append(f"  {status_icon} {p['name']}（{p['stage']}，{p['milestone_pct']}%，{p['owner']}）")
        if high_risk:
            recs.append(f"🚨 {len(high_risk)} 个项目需重点关注：")
            for p in high_risk:
                note = p.get("risk_note", f"里程碑进度 {p['milestone_pct']}%")
                recs.append(f"   → {p['name']}：{note}")
        if actions_taken:
            recs.append("🔄 已生成 NPI 加速推进行动项（授权内自动）：")
            for a in actions_taken:
                recs.append(f"   → {a['detail']}")
        recs.append("📋 建议将 NPI 进度纳入月度产品评审（PCR），按风险等级排序推进")
        return recs


npi_agent = NpiAgent()
