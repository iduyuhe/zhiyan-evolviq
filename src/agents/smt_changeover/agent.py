"""SMT换线Agent——换线优化与料站预配置

目标场景：SMT产线换线效率优化
能力范围：
1. 换线计划生成（基于生产排程+物料齐套）
2. 料站预配置（Feeder分配+站位优化）
3. 换线检查清单自动生成
4. 换线时间预估与优化建议
5. SMED(快速换线)分析

数据层：通过 SMTChangeoverTools 从 data/seed/smt_changeover.json 加载，可切换真实MCP(MES)。
"""

import logging

from src.agents.smt_changeover.tools import SMTChangeoverTools

logger = logging.getLogger(__name__)


class SMTChangeoverAgent:
    """SMT换线优化Agent"""

    def __init__(self):
        self.tools = SMTChangeoverTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「SMT换线Agent」，专注SMT产线换线优化与料站预配置。

## 核心能力
1. 换线计划生成（基于生产排程+物料齐套状态）
2. 料站预配置（Feeder分配+站位优化+钢网/程序准备）
3. 换线检查清单自动生成（防遗漏）
4. 换线时间预估与关键路径分析
5. SMED(快速换线)分析——内部时间转外部时间

## 工作原则
- SMED优先：尽可能将内部作业转为外部作业
- 并行化：可并行的步骤标注并行执行
- 防错：检查清单覆盖所有关键确认项
- 目标：换线时间≤45分钟（行业标杆35分钟）
"""

    async def analyze(self, goal: str) -> dict:
        """执行换线分析（可复现，无随机）"""
        logger.info(f"[SMT Changeover Agent] Analyzing: {goal[:60]}...")

        plan_key = self._match_plan(goal)
        plan = await self.tools.get_changeover_plan(plan_key) or await self.tools.get_changeover_plan(list(self.tools._plans.keys())[0])
        line = await self.tools.get_line_config(plan["line_id"]) or {}

        history = line.get("current_setup", {}).get("changeover_history_min", [])
        avg_history = round(sum(history) / len(history), 1) if history else 0
        improvement = round(avg_history - plan["estimated_time_min"], 1)

        smed = plan["smed_analysis"]
        optimized_time = plan["estimated_time_min"] - smed["smed_potential_min"]

        # 生成换线执行工单（真实动作）
        workorder = await self.tools.create_changeover_plan(plan_key, plan["line_id"])
        actions_taken = [{
            "type": "create_changeover_plan",
            "detail": f"生成换线工单 {workorder.get('workorder_id', '')}（{plan['from_product']}→{plan['to_product']}）",
            "line_id": plan["line_id"],
            "confidence": 0.85,
        }]

        return {
            "status": "completed",
            "summary": f"换线计划生成：{plan['from_product']}→{plan['to_product']}，预估{plan['estimated_time_min']}分钟（历史平均{avg_history}分钟，SMED优化后可降至{optimized_time}分钟）",
            "line_id": plan["line_id"],
            "line_name": line.get("name", plan["line_id"]),
            "from_product": plan["from_product"],
            "to_product": plan["to_product"],
            "feeder_changes": plan["feeder_changes"],
            "tray_changes": plan["tray_changes"],
            "stencil_change": plan["stencil_change"],
            "stencil_id": plan["stencil_id"],
            "program_load": plan["program_load"],
            "estimated_time_min": plan["estimated_time_min"],
            "avg_history_time_min": avg_history,
            "improvement_min": improvement,
            "critical_path": plan["critical_path"],
            "smed_analysis": smed,
            "optimized_time_min": optimized_time,
            "checklist": plan["checklist"],
            "recommendations": self._generate_recommendations(plan, optimized_time),
            "actions_taken": actions_taken,
        }

    def _match_plan(self, goal: str) -> str:
        """匹配换线计划（基于已加载的种子键，无随机）"""
        goal_upper = goal.upper()
        for key in self.tools._plans:
            if key.upper() in goal_upper:
                return key
        if "PCB-C" in goal_upper or "L01" in goal:
            return "PCB-A-v3.2→PCB-C-v2.0"
        if "PCB-A" in goal_upper or "L02" in goal:
            return "PCB-B-v1.8→PCB-A-v3.2"
        return "PCB-A-v3.2→PCB-C-v2.0"

    def _generate_recommendations(self, plan: dict, optimized_time: int) -> list:
        """生成换线优化建议"""
        recs = []
        smed = plan["smed_analysis"]

        recs.append(f"⏱️ 当前预估换线时间{plan['estimated_time_min']}分钟，SMED优化后可降至{optimized_time}分钟（节省{smed['smed_potential_min']}分钟）")

        for suggestion in smed["smed_suggestions"]:
            recs.append(f"🔧 SMED建议：{suggestion}")

        if optimized_time <= 35:
            recs.append("✅ 优化后可达行业标杆水平(35分钟)")
        elif optimized_time <= 45:
            recs.append("⚠️ 优化后接近行业标杆，仍有改善空间")
        else:
            recs.append("🔴 优化后仍高于目标，建议增加Feeder预组装人手")

        recs.append("📋 建议使用换线检查清单逐项确认，防止遗漏")
        recs.append("🔄 换线后收集实际时间数据，持续优化SMED方案")
        return recs


smt_changeover_agent = SMTChangeoverAgent()
