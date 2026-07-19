"""AOI判定Agent——SMT AOI误报智能过滤与检测优化

目标场景：SMT产线AOI自动光学检测误报率优化
能力范围：
1. AOI检测结果智能分析（良品/不良品特征学习）
2. 误报识别与过滤（区分真缺陷与误报）
3. 检测阈值动态优化建议
4. 缺陷类型分布统计与趋势分析
5. 复判效率提升（减少人工复判工作量）

数据层：通过 AOITools 从 data/seed/aoi_results.json 加载，可切换真实MCP(AOI/SPC)。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.aoi_judge.tools import AOITools

logger = logging.getLogger(__name__)


class AOIAgent(BaseAgent):
    """AOI判定Agent"""

    name = "aoi_judge"
    description = "AOI 误报智能过滤与检测阈值优化"

    def __init__(self):
        self.tools = AOITools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「AOI判定Agent」，专注SMT产线AOI误报智能过滤与检测优化。

## 核心能力
1. AOI检测结果智能分析（误报率统计+缺陷分类）
2. 误报根因分析（算法灵敏度/光源干扰/工艺参数）
3. 检测阈值动态优化建议（平衡漏检与误报）
4. 缺陷趋势追踪（按类型/位置/时间段）
5. 复判效率提升（减少人工复判工时）

## 工作原则
- 误报率目标：从30-50%降至20-25%（工业极限低于15%需极高成本）
- 安全第一：降低误报的同时不能增加漏检风险
- 数据驱动：阈值调整建议基于统计分析
- 持续优化：每次阈值调整后需跟踪验证效果
"""

    async def analyze(self, goal: str) -> dict:
        """执行AOI误报分析（可复现，无随机）"""
        logger.info(f"[AOI Agent] Analyzing: {goal[:60]}...")

        line_id = self._match_line(goal)
        data = await self.tools.get_line_result(line_id) or list(self.tools._results.values())[0]

        categories = []
        for cat in data["defect_categories"]:
            categories.append({
                "type": cat["type"],
                "total_calls": cat["total_calls"],
                "true_defects": cat["true_defects"],
                "false_alarms": cat["false_alarms"],
                "false_alarm_rate": cat["false_alarm_rate"],
                "common_location": cat["common_location"],
                "root_cause": cat["root_cause"],
                "threshold_suggestion": cat["threshold_suggestion"],
            })

        # 优化后预期误报率（固定优化系数，可复现）
        factor = self.tools._optim_factor
        optimized_false_alarms = int(data["false_alarms"] * factor)
        optimized_rate = round(optimized_false_alarms / (data["true_defects"] + optimized_false_alarms) * 100, 1)
        optimized_review_time = round(data["operator_review_time_min"] * factor, 0)

        # 生成阈值优化任务（真实动作）
        top_suggestions = [c["threshold_suggestion"] for c in sorted(categories, key=lambda x: x["false_alarms"], reverse=True)[:3]]
        task = await self.tools.create_threshold_optimization(line_id, top_suggestions)
        actions_taken = [{
            "type": "optimize_aoi_threshold",
            "detail": f"为 {data['line_name']} 生成AOI阈值优化任务（{task.get('task_id', '')}，{len(top_suggestions)}项建议）",
            "line_id": line_id,
            "confidence": 0.78,
        }]

        return {
            "status": "completed",
            "summary": f"AOI误报分析完成：{data['line_name']}当前误报率{data['false_alarm_rate']}%，优化后预计降至{optimized_rate}%，可节省复判工时{data['operator_review_time_min'] - optimized_review_time:.0f}分钟/班",
            "line_id": line_id,
            "line_name": data["line_name"],
            "product": data["product"],
            "total_inspections": data["total_inspections"],
            "total_calls": data["total_calls"],
            "true_defects": data["true_defects"],
            "false_alarms": data["false_alarms"],
            "false_alarm_rate": data["false_alarm_rate"],
            "optimized_false_alarm_rate": optimized_rate,
            "defect_categories": categories,
            "operator_review_time_min": data["operator_review_time_min"],
            "optimized_review_time_min": optimized_review_time,
            "review_time_saved_min": round(data["operator_review_time_min"] - optimized_review_time, 0),
            "operator_count": data["operator_count"],
            "recommendations": self._generate_recommendations(data, optimized_rate, optimized_review_time),
            "actions_taken": actions_taken,
        }

    def _match_line(self, goal: str) -> str:
        """匹配产线（基于已加载的种子键，无随机）"""
        if "L02" in goal or "2" in goal:
            return "SMT-L02" if "SMT-L02" in self.tools._results else list(self.tools._results.keys())[0]
        return "SMT-L01" if "SMT-L01" in self.tools._results else list(self.tools._results.keys())[0]

    def _generate_recommendations(self, data: dict, optimized_rate: float, optimized_time: float) -> list:
        """生成优化建议"""
        recs = []

        recs.append(f"📊 当前误报率{data['false_alarm_rate']}%，优化后预计{optimized_rate}%（降低{data['false_alarm_rate'] - optimized_rate:.1f}个百分点）")

        sorted_cats = sorted(data["defect_categories"], key=lambda x: x["false_alarms"], reverse=True)
        top_cat = sorted_cats[0]
        recs.append(f"🎯 最大误报来源：{top_cat['type']}（误报{top_cat['false_alarms']}个），建议优先优化")

        for cat in sorted_cats[:3]:
            recs.append(f"🔧 {cat['type']}：{cat['threshold_suggestion']}")

        time_saved = data["operator_review_time_min"] - optimized_time
        recs.append(f"⏱️ 复判工时优化：从{data['operator_review_time_min']}分钟降至{optimized_time:.0f}分钟/班，节省{time_saved:.0f}分钟")
        recs.append(f"👥 可将{data['operator_count']}名复判人员中1人转岗至首件检验，提升整体品质管控")

        recs.append("⚠️ 注意：阈值调整后需连续跟踪3天，确认漏检率未上升")
        recs.append("📋 建议建立AOI阈值月度评审机制，持续优化检测参数")
        return recs


aoi_agent = AOIAgent()
