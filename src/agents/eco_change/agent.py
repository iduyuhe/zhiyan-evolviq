"""ECO变更Agent——工程变更指令(ECO/ECN)影响分析

目标场景：电子制造工程变更管理自动化
能力范围：
1. 变更内容解析（物料替换/工艺修改/设计更新）
2. 受影响物料识别（BOM层级展开+在制库存）
3. 受影响工序识别（工艺路线+设备配置）
4. 在制库存影响评估（WIP/成品/在途）
5. 变更通知自动分发（跨部门协同）
6. 变更风险评估与实施计划生成

数据层：通过 ECOTools 从 data/seed/eco_cases.json 加载，可切换真实MCP(PLM/ERP)。
"""

import logging

from src.agents.eco_change.tools import ECOTools

logger = logging.getLogger(__name__)


class ECOAgent:
    """ECO变更Agent"""

    def __init__(self):
        self.tools = ECOTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「ECO变更Agent」，专注工程变更指令(ECO/ECN)的影响分析与协同管理。

## 核心能力
1. 变更内容自动解析（物料替换/工艺修改/设计更新）
2. 受影响范围识别（BOM展开+WIP+库存+工序）
3. 在制库存影响评估（原材料/WIP/成品/在途PO）
4. 变更通知自动分发（跨部门协同）
5. 变更风险评估（进度/成本/质量/客户影响）
6. 实施计划生成（分部门行动项+截止日期）

## 工作原则
- 全面评估：变更影响必须覆盖BOM/WIP/库存/工序/客户全维度
- 风险分级：高优先级变更需CFT(跨功能团队)评审
- 库存消化：旧物料库存需制定明确消化计划
- 可追溯：每次变更完整记录影响范围和行动项
"""

    async def analyze(self, goal: str) -> dict:
        """执行ECO变更影响分析（可复现，无随机）"""
        logger.info(f"[ECO Agent] Analyzing: {goal[:60]}...")

        eco_id = self._match_eco(goal)
        eco = await self.tools.get_case(eco_id) or await self.tools.get_case(list(self.tools._cases.keys())[0])

        affected_items = []
        inv = eco["affected_inventory"]

        if inv.get("raw_material_old"):
            affected_items.append({
                "category": "原材料(旧)",
                "part": inv["raw_material_old"]["part"],
                "qty": inv["raw_material_old"]["qty"],
                "value_usd": inv["raw_material_old"]["value_usd"],
                "action": "标记为受限库存，制定消化计划",
            })
        if inv.get("raw_material_new"):
            affected_items.append({
                "category": "原材料(新)",
                "part": inv["raw_material_new"]["part"],
                "qty": inv["raw_material_new"]["qty"],
                "value_usd": inv["raw_material_new"]["value_usd"],
                "action": "确认库存充足，可用于切换",
            })
        if inv.get("wip") and inv["wip"].get("qty", 0) > 0:
            affected_items.append({
                "category": "在制品(WIP)",
                "part": eco["affected_boms"][0],
                "qty": inv["wip"]["qty"],
                "value_usd": inv["wip"]["value_usd"],
                "action": f"当前阶段: {inv['wip']['stage']}",
            })
        if inv.get("finished_goods") and inv["finished_goods"].get("qty", 0) > 0:
            affected_items.append({
                "category": "成品库存",
                "part": eco["affected_boms"][0],
                "qty": inv["finished_goods"]["qty"],
                "value_usd": inv["finished_goods"]["value_usd"],
                "action": f"当前阶段: {inv['finished_goods']['stage']}",
            })
        if inv.get("in_transit_po") and inv["in_transit_po"].get("po"):
            po = inv["in_transit_po"]
            affected_items.append({
                "category": "在途PO",
                "part": po["part"],
                "qty": po["qty"],
                "value_usd": 0,
                "action": f"PO: {po['po']}, ETA: {po.get('eta', 'N/A')}, 建议取消",
            })

        risk = eco["risk_assessment"]
        departments = list(set(a["dept"] for a in eco["required_actions"]))

        # 创建ECO任务 + 跨部门分发通知（真实动作）
        task = await self.tools.create_eco_task(eco_id)
        notice = await self.tools.dispatch_notice(eco_id, departments)
        actions_taken = [
            {
                "type": "create_eco_task",
                "detail": f"创建ECO执行任务 {task.get('task_id', '')}",
                "eco_id": eco_id,
                "confidence": 0.86,
            },
            {
                "type": "dispatch_eco_notice",
                "detail": f"向 {len(departments)} 个部门分发变更通知（{notice.get('status', 'dispatched')}）：{', '.join(departments)}",
                "eco_id": eco_id,
                "departments": departments,
                "confidence": 0.83,
            },
        ]

        return {
            "status": "completed",
            "summary": f"ECO变更分析完成：{eco['title']}，影响{len(eco['affected_boms'])}个BOM，{len(eco['affected_work_orders'])}个工单",
            "eco_id": eco_id,
            "title": eco["title"],
            "type": eco["type"],
            "initiator": eco["initiator"],
            "priority": eco["priority"],
            "change_detail": eco["change_detail"],
            "affected_boms": eco["affected_boms"],
            "affected_work_orders": eco["affected_work_orders"],
            "affected_items": affected_items,
            "required_actions": eco["required_actions"],
            "risk_assessment": risk,
            "departments_involved": departments,
            "inventory_exposure_usd": risk.get("inventory_exposure_usd", 0),
            "annual_savings_usd": risk.get("annual_savings_usd", 0),
            "actions_taken": actions_taken,
        }

    def _match_eco(self, goal: str) -> str:
        """匹配ECO案例（基于已加载的种子键，无随机）"""
        goal_upper = goal.upper()
        for eco_id in self.tools._cases:
            if eco_id in goal_upper:
                return eco_id
        if "MCU" in goal_upper or "STM32" in goal_upper or "GD32" in goal_upper:
            return "ECO-2026-045"
        if "阻焊" in goal or "工艺" in goal:
            return "ECO-2026-046"
        return "ECO-2026-045"


eco_agent = ECOAgent()
