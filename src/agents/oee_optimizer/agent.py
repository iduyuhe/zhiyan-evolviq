"""OEE优化Agent——产线综合设备效率(OEE)实时监控与优化

目标场景：SMT产线OEE实时监控与改善
能力范围：
1. OEE三要素计算（可用率×性能率×质量率）
2. 六大损失分析（设备停机/换线/速度损失/小停机/不良/启动）
3. 瓶颈设备识别
4. 改善建议推送
5. 产线效率趋势分析

数据层：通过 OEETools 从 data/seed/oee_lines.json 加载，可切换真实MCP(MES/Andon)。
"""

import logging

from src.agents.oee_optimizer.tools import OEETools

logger = logging.getLogger(__name__)


class OEEAgent:
    """OEE优化Agent"""

    def __init__(self):
        self.tools = OEETools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「OEE优化Agent」，专注SMT产线综合设备效率监控与优化。

## 核心能力
1. OEE三要素实时计算（可用率 × 性能率 × 质量率）
2. 六大损失分析（设备故障/换线/速度损失/小停机/不良/启动报废）
3. 瓶颈设备识别与改善优先级排序
4. 改善建议推送（基于损失分析自动生成）
5. 产线效率趋势追踪与目标对标

## 工作原则
- OEE目标：≥85%（世界级制造水平）
- 数据驱动：每个损失项必须有量化数据支撑
- 优先级：损失工时最大的项优先改善
- 持续改善：每次改善后重新计算OEE验证效果
"""

    async def analyze(self, goal: str) -> dict:
        """执行OEE分析（可复现，无随机）"""
        logger.info(f"[OEE Agent] Analyzing: {goal[:60]}...")

        line_ids = self._match_lines(goal)
        targets = await self.tools.get_targets()

        results = []
        total_oee = 0
        bottleneck_line = None
        worst_oee = 100

        for line_id in line_ids:
            line = await self.tools.get_line(line_id)
            if not line:
                continue

            availability = self._calc_availability(line)
            performance = self._calc_performance(line)
            quality = self._calc_quality(line)
            oee = round(availability * performance * quality / 10000, 1)

            loss_analysis = self._analyze_losses(line)

            results.append({
                "line_id": line_id,
                "line_name": line["name"],
                "product": line["product"],
                "oee": oee,
                "availability": availability,
                "performance": performance,
                "quality": quality,
                "actual_output": line["actual_output"],
                "defect_rate": round(line["defect_units"] / line["total_units"] * 100, 2),
                "losses": loss_analysis,
                "gap_to_target": round(oee - targets["oee"], 1),
                "status": "excellent" if oee >= 85 else "good" if oee >= 70 else "warning" if oee >= 60 else "critical",
            })

            total_oee += oee
            if oee < worst_oee:
                worst_oee = oee
                bottleneck_line = line["name"]

        avg_oee = round(total_oee / len(results), 1) if results else 0

        # 针对低于目标的产线生成改善任务（真实动作）
        actions_taken = []
        for r in results:
            if r["oee"] < targets["oee"]:
                max_loss = max(r["losses"], key=lambda x: x.get("impact_hours", 0))
                task = await self.tools.create_improvement_task(r["line_id"], max_loss["name"])
                actions_taken.append({
                    "type": "create_improvement_task",
                    "detail": f"为 {r['line_name']} 创建改善任务：聚焦{max_loss['name']}（{task.get('task_id', '')}）",
                    "line_id": r["line_id"],
                    "confidence": 0.82,
                })

        recommendations = self._generate_recommendations(results, targets)

        return {
            "status": "completed",
            "summary": f"OEE分析完成：{len(results)}条产线，平均OEE {avg_oee}%，瓶颈产线: {bottleneck_line}",
            "avg_oee": avg_oee,
            "oee_target": targets["oee"],
            "gap_to_target": round(avg_oee - targets["oee"], 1),
            "bottleneck": bottleneck_line,
            "lines": results,
            "recommendations": recommendations,
            "targets": targets,
            "actions_taken": actions_taken,
        }

    def _match_lines(self, goal: str) -> list:
        """匹配产线（基于已加载的种子键，无随机）"""
        all_ids = list(self.tools._lines.keys())
        if "全部" in goal or "all" in goal.lower() or "oee" in goal.lower():
            return all_ids
        if "L01" in goal or "1" in goal:
            return ["SMT-L01"] if "SMT-L01" in all_ids else all_ids
        if "L02" in goal or "2" in goal:
            return ["SMT-L02"] if "SMT-L02" in all_ids else all_ids
        if "L03" in goal or "3" in goal:
            return ["SMT-L03"] if "SMT-L03" in all_ids else all_ids
        return all_ids

    def _calc_availability(self, line: dict) -> float:
        """可用率 = (计划时间 - 停机时间) / 计划时间"""
        planned = line["planned_hours"]
        downtime = line["downtime_hours"]
        return round((planned - downtime) / planned * 100, 1)

    def _calc_performance(self, line: dict) -> float:
        """性能率 = 实际速度 / 理论速度"""
        planned_minutes = (line["planned_hours"] - line["downtime_hours"]) * 60
        ideal_output = line["ideal_speed_uph"] / 60 * planned_minutes
        return round(line["actual_output"] / ideal_output * 100, 1)

    def _calc_quality(self, line: dict) -> float:
        """质量率 = (总产出 - 不良) / 总产出"""
        return round((line["total_units"] - line["defect_units"]) / line["total_units"] * 100, 1)

    def _analyze_losses(self, line: dict) -> list:
        """六大损失分析"""
        losses = line["losses"]
        return [
            {"name": "设备故障", "type": "availability", "impact_hours": losses["equipment_failure"]["hours"], "detail": losses["equipment_failure"]["desc"]},
            {"name": "换线调试", "type": "availability", "impact_hours": losses["setup_adjustment"]["hours"], "detail": losses["setup_adjustment"]["desc"]},
            {"name": "小停机", "type": "availability", "impact_hours": losses["idling_minor"]["hours"], "detail": losses["idling_minor"]["desc"]},
            {"name": "速度损失", "type": "performance", "impact_uph": losses["speed_loss"]["uph_diff"], "detail": losses["speed_loss"]["desc"]},
            {"name": "过程不良", "type": "quality", "impact_qty": losses["process_defect"]["qty"], "detail": losses["process_defect"]["desc"]},
            {"name": "启动报废", "type": "quality", "impact_qty": losses["startup_yield"]["qty"], "detail": losses["startup_yield"]["desc"]},
        ]

    def _generate_recommendations(self, results: list, targets: dict) -> list:
        """生成改善建议"""
        recs = []
        for r in results:
            if r["oee"] < targets["oee"]:
                recs.append(f"📍 {r['line_name']} OEE {r['oee']}%（低于目标{targets['oee']}%），需改善")

                max_loss = max(r["losses"], key=lambda x: x.get("impact_hours", 0))
                if max_loss["type"] == "availability":
                    recs.append(f"   → 可用率瓶颈：{max_loss['name']}损失{max_loss['impact_hours']}h，{max_loss['detail']}")
                elif max_loss["type"] == "performance":
                    recs.append(f"   → 性能瓶颈：{max_loss['name']}损失{max_loss.get('impact_uph', 0)}UPH，{max_loss['detail']}")

                if r["availability"] < targets["availability"]:
                    recs.append(f"   → 可用率{r['availability']}% < 目标{targets['availability']}%，建议优化换线流程(SMED)")
                if r["performance"] < targets["performance"]:
                    recs.append(f"   → 性能率{r['performance']}% < 目标{targets['performance']}%，建议优化贴装速度参数")
                if r["quality"] < targets["quality"]:
                    recs.append(f"   → 质量率{r['quality']}% < 目标{targets['quality']}%，建议优化印刷工艺+首件检验")
            else:
                recs.append(f"✅ {r['line_name']} OEE {r['oee']}%，达标")

        recs.append("📋 建议每周召开OEE改善会议，针对瓶颈产线制定专项改善计划")
        return recs


oee_agent = OEEAgent()
