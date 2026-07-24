"""采购与供应商管理 Agent——供应商绩效、合同管理、采购策略

企业级「经营决策大脑」第九部分：把供应商全维度绩效（交期/质量/成本/合规）、
合同价值与到期、采购策略执行结构化，识别低绩效供应商并授权内自动生成评审。

数据层：通过 ProcurementTools 从种子数据加载（可切换真实 SRM/ERP 系统）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.procurement_manage.tools import ProcurementTools

logger = logging.getLogger(__name__)


class ProcurementAgent(BaseAgent):
    """采购与供应商管理 Agent"""

    name = "procurement_manage"
    description = "供应商绩效评分（交期/质量/成本/合规）、合同管理与采购策略执行"

    def __init__(self):
        self.tools = ProcurementTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「采购与供应商管理 Agent」，专注制造企业的战略采购(SRM)管理。

## 核心能力
1. 供应商绩效看板：综合评分、交期/质量/成本/合规四维
2. 合同管理：合同金额、到期时间、自动续约状态
3. 采购策略：国产替代、长协降本、供应商淘汰等策略执行进度
4. 授权内自动评审：对低绩效供应商(C/D 级)自动生成供应商评审任务(create_supplier_review)

## 工作原则
- 供应商即产能：交期不畅=产线停摆，质量不稳=良率下降
- 战略采购：不只看单价，看总拥有成本(TCO)
- 不臆造数字：所有数字来自种子/SRM 系统（事实锚点）
"""

    async def analyze(self, goal: str) -> dict:
        logger.info(f"[Procurement Agent] Analyzing: {goal[:60]}...")

        suppliers = await self.tools.get_suppliers()
        contracts = await self.tools.get_contracts()
        strategies = await self.tools.get_strategy_items()

        avg_score = round(sum(s["score"] for s in suppliers) / len(suppliers), 1)
        low_performers = [s for s in suppliers if s["tier"] in ("C", "D") or s["score"] < 70]
        expiring_soon = [c for c in contracts if not c["auto_renew"]]
        total_contract_value = sum(c["value_wan"] for c in contracts)

        actions_taken = []
        for s in low_performers:
            reason = s.get("risk_note", f"综合评分 {s['score']}，低于 70 分阈值")
            task = await self.tools.create_supplier_review(s["id"], reason)
            actions_taken.append({
                "type": "create_supplier_review",
                "detail": f"为 {s['name']}（{reason}）生成供应商评审任务",
                "supplier_id": s["id"],
                "confidence": 0.84,
                "status": "auto_executed",
            })

        recommendations = self._generate_recommendations(
            suppliers, contracts, strategies, avg_score, low_performers, expiring_soon, actions_taken
        )

        return {
            "status": "completed",
            "summary": (
                f"采购分析完成：{len(suppliers)} 家供应商，平均综合评分 {avg_score}；"
                f"合同总金额 {total_contract_value} 万元，{len(expiring_soon)} 份合同不自动续约；"
                f"{len(low_performers)} 家低绩效供应商已自动生成评审任务"
            ),
            "supplier_count": len(suppliers),
            "avg_score": avg_score,
            "low_performer_count": len(low_performers),
            "total_contract_value_wan": total_contract_value,
            "expiring_contracts": len(expiring_soon),
            "suppliers": suppliers,
            "contracts": contracts,
            "strategies": strategies,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _generate_recommendations(self, suppliers, contracts, strategies, avg_score,
                                  low_performers, expiring_soon, actions_taken) -> list:
        recs = []
        recs.append(f"🏭 {len(suppliers)} 家供应商，平均评分 {avg_score}（合同总额 {sum(c['value_wan'] for c in contracts)} 万元）")
        for s in suppliers:
            icon = "✅" if s["tier"] in ("A",) else "⚠️" if s["tier"] == "B" else "🚨"
            recs.append(f"  {icon} {s['name']}（{s['category']}） 评分 {s['score']} 交期{s['delivery']} 质量{s['quality']} 成本{s['cost']}")
        if low_performers:
            recs.append(f"🚨 {len(low_performers)} 家低绩效供应商：")
            for s in low_performers:
                note = s.get("risk_note", f"评分 {s['score']}")
                recs.append(f"   → {s['name']}：{note}")
        if actions_taken:
            recs.append("🔄 已生成供应商评审任务（授权内自动）：")
            for a in actions_taken:
                recs.append(f"   → {a['detail']}")
        recs.append("📋 建议将供应商绩效纳入季度采购评审，按评分排序推进")
        return recs


procurement_agent = ProcurementAgent()
