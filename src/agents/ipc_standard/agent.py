"""IPC标准Agent——IPC标准辅助查询与缺陷判定

目标场景：电子制造品质检验IPC标准实时查询
能力范围：
1. IPC标准条款检索（IPC-A-610/IPC-2222/IPC-2221等）
2. 缺陷等级自动判定（Class 1/2/3）
3. 标准条款解读与适用场景说明
4. 检验规范一致性辅助（减少人工判定差异）
5. 标准更新提醒与培训建议

数据层：通过 IPCStandardTools 从 data/seed/ipc_standards.json 加载，可切换真实MCP(PLM)。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.ipc_standard.tools import IPCStandardTools

logger = logging.getLogger(__name__)


class IPCStandardAgent(BaseAgent):
    """IPC标准Agent"""

    name = "ipc_standard"
    description = "IPC 标准辅助查询与缺陷等级判定"

    def __init__(self):
        self.tools = IPCStandardTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「IPC标准Agent」，专注电子制造IPC标准的辅助查询与缺陷判定。

## 核心能力
1. IPC标准条款检索（IPC-A-610/IPC-2222等）
2. 缺陷等级自动判定（Class 1/2/3三级标准）
3. 标准条款解读与检验方法说明
4. 检验规范一致性辅助（减少人工判定差异）
5. 标准更新提醒与培训建议

## 工作原则
- 标准驱动：每项判定必须引用具体IPC标准条款
- 分级判定：明确区分Class 1(通用)/Class 2(专用)/Class 3(高性能)的判定标准
- 可追溯：判定结果附带标准编号、条款编号和检验方法
- 一致性：同一缺陷在不同检验员间判定结果应一致
"""

    async def analyze(self, goal: str) -> dict:
        """执行IPC标准查询与判定（可复现，无随机）"""
        logger.info(f"[IPC Standard Agent] Analyzing: {goal[:60]}...")

        matched = await self.tools.match_judgment(goal)
        if not matched:
            return {
                "status": "completed",
                "summary": "未匹配到相关IPC条款，请补充缺陷类型或标准编号",
                "query": goal,
                "standards_available": await self.tools.list_standards(),
                "recommendations": ["📋 建议使用标准编号（如 IPC-A-610）或更具体的缺陷类型查询"],
            }

        standard_id = matched["matched_standard"]
        standard = await self.tools.get_standard(standard_id) or {}
        category_name = matched["matched_category"]

        matched_criteria = await self.tools.search_criteria(
            standard_id, category_name, matched["judgment"]["defect_type"]
        )

        # 若缺陷在任一Class下均不可接受（判定为需返修），生成培训任务（真实动作）
        j = matched["judgment"]
        actions_taken = []
        is_universal_defect = any(
            "defect" in str(j.get(f"class_{n}_limit", "")) for n in (1, 2, 3)
        )
        if is_universal_defect:
            task = await self.tools.create_training_task(standard_id, j["defect_type"])
            actions_taken.append({
                "type": "create_training_task",
                "detail": f"针对「{j['defect_type']}」生成检验员培训任务（{task.get('task_id', '')}）",
                "standard_id": standard_id,
                "confidence": 0.8,
            })

        return {
            "status": "completed",
            "summary": f"IPC标准查询完成：{matched['judgment']['defect_type']}（{standard_id} {category_name}）",
            "query": goal,
            "matched_standard": standard_id,
            "standard_name": standard.get("name", standard_id),
            "standard_version": standard.get("version", ""),
            "matched_category": category_name,
            "judgment": matched["judgment"],
            "criteria_detail": matched_criteria,
            "standards_available": await self.tools.list_standards(),
            "recommendations": self._generate_recommendations(matched),
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, matched: dict) -> list:
        """生成建议"""
        recs = []
        j = matched["judgment"]

        recs.append(f"📋 判定标准：{matched['matched_standard']} {matched['matched_category']}")

        if "class_1_limit" in j:
            recs.append(f"   Class 1（通用）：{j['class_1_limit']}")
        if "class_2_limit" in j:
            recs.append(f"   Class 2（专用服务）：{j['class_2_limit']}")
        if "class_3_limit" in j:
            recs.append(f"   Class 3（高性能）：{j['class_3_limit']}")

        if "defect" in str(j.get("class_1_limit", "")):
            recs.append("⚠️ 该缺陷在所有Class下均为不可接受，必须返修")

        if "inspection_method" in j:
            recs.append(f"🔍 推荐检验方法：{j['inspection_method']}")

        recs.append("📖 建议定期组织IPC标准培训，确保检验员判定一致性≥95%")
        recs.append("🔄 IPC标准约3-5年更新一次，建议关注最新版本变化")
        return recs


ipc_standard_agent = IPCStandardAgent()
