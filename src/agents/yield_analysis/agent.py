"""良率分析Agent——晶圆良率趋势分析与缺陷根因定位

目标场景：SMIC晶圆厂的良率管理、缺陷定位、工艺参数优化建议。
能力范围：
1. 良率趋势分析（按批次/工艺/设备维度）
2. 缺陷分类与根因定位（基于缺陷分布）
3. 工艺参数-良率关联分析
4. 改进建议与DOE实验生成

数据层：通过 YieldTools 从 data/seed/yield_data.json 加载，可切换真实MCP(YMS/KLA)。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.yield_analysis.tools import YieldTools

logger = logging.getLogger(__name__)


class YieldAgent(BaseAgent):
    """良率分析Agent"""

    name = "yield_analysis"
    description = "晶圆良率趋势分析与缺陷根因定位"

    def __init__(self):
        self.tools = YieldTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「良率分析Agent」，专注半导体晶圆制造的良率管理与缺陷分析。

## 当前服务客户：中芯国际 SMIC
- 工艺节点：28nm及以上成熟制程
- 良率目标：关键产品良率≥95%
- 管理重点：颗粒污染控制、光刻工艺窗口、刻蚀均匀性

## 核心能力
1. 良率趋势跟踪（按批次/时间/工艺维度）
2. 缺陷分类统计（颗粒/桥连/残留/划伤）
3. 设备-良率关联分析（定位低良率设备）
4. 改进建议生成（基于缺陷模式匹配）

## 工作原则
- 根因导向：不只展示数据，要定位根因
- 可量化：每条建议必须有数据支撑
- 优先级：良率低于目标的产品优先分析
"""

    async def analyze(self, goal: str) -> dict:
        """分析良率数据"""
        logger.info(f"[Yield Agent] Analyzing: {goal[:60]}...")

        product = await self._match_product(goal)
        if not product:
            return {"status": "completed", "summary": "未匹配到产品", "findings": [], "recommendations": []}

        current_yield = product["current_yield"]
        gap = round(product["target_yield"] - current_yield, 1)

        findings = []
        recommendations = []
        actions_taken = []

        # 缺陷趋势分析
        for defect in product["defect_top3"]:
            if defect["trend"] == "上升中":
                findings.append(f"🔴 {defect['type']}占比{defect['ratio']}%，呈上升趋势，需重点关注")
                recommendations.append(f"建议对{defect['type']}相关工艺参数进行DOE实验，优化窗口")
                actions_taken.append({
                    "type": "create_doe_experiment",
                    "detail": f"针对[{defect['type']}]创建DOE实验（{product['name']}）",
                    "defect_type": defect["type"],
                    "confidence": 0.79,
                })
            elif defect["trend"] == "下降中":
                findings.append(f"🟢 {defect['type']}占比{defect['ratio']}%，控制措施有效")
            else:
                findings.append(f"🟡 {defect['type']}占比{defect['ratio']}%，趋势稳定")

        # 设备差异分析
        for eq in product["by_equipment"]:
            if eq["status"] == "attention":
                findings.append(f"🟠 {eq['equipment']}良率{eq['yield']}%，低于平均值，建议排查")
                recommendations.append(f"安排{eq['equipment']}的PM检查和校准")

        if gap > 0:
            top_defect = max(product["defect_top3"], key=lambda d: d["ratio"])
            recommendations.append(
                f"距离{product['target_yield']}%目标还差{gap}个百分点，"
                f"建议优先解决{top_defect['type']}问题"
            )

        return {
            "status": "completed",
            "summary": f"良率分析完成：{product['name']} 当前{current_yield}%，目标{product['target_yield']}%，差距{gap}个百分点",
            "product": product["name"],
            "node": product.get("node", ""),
            "current_yield": current_yield,
            "target_yield": product["target_yield"],
            "gap": gap,
            "trend": product.get("trend", []),
            "defects": product["defect_top3"],
            "by_equipment": product["by_equipment"],
            "findings": findings,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    async def _match_product(self, goal: str) -> dict | None:
        """从目标文本匹配产品，默认取良率最低（最需关注）的产品"""
        products = await self.tools.get_product_list()
        if not products:
            return None
        goal_lower = goal.lower()
        for p in products:
            if p.get("node", "").lower() in goal_lower or p["name"].lower() in goal_lower:
                return p
        # 默认返回良率缺口最大的产品（最需分析）
        return min(products, key=lambda x: x["current_yield"] - x["target_yield"])


yield_agent = YieldAgent()
