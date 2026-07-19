"""BOM选型Agent——元器件智能选型+替代推荐

目标场景：电子研发BOM选型优化
能力范围：
1. 元器件参数匹配与选型推荐
2. 兼容替代料检索（同参数/同封装/同功能）
3. 历史用量与供应链稳定性评估
4. 价格趋势分析与成本优化建议
5. 生命周期状态检查（EOL/NRND预警）

数据层：通过 BOMSelectorTools 从 data/seed/components.json 加载，可切换真实MCP(PLM/ERP)。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.bom_selector.tools import BOMSelectorTools

logger = logging.getLogger(__name__)


class BOMSelectorAgent(BaseAgent):
    """BOM选型Agent"""

    name = "bom_selector"
    description = "元器件智能选型 + 兼容替代推荐"

    def __init__(self):
        self.tools = BOMSelectorTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「BOM选型Agent」，专注元器件智能选型与替代推荐。

## 核心能力
1. 元器件参数匹配与选型推荐
2. 兼容替代料检索（pin-to-pin / 功能兼容）
3. 供应链稳定性评估（库存/交期/月用量）
4. 价格趋势分析与成本优化
5. 生命周期状态检查（EOL/NRND预警）

## 工作原则
- 国产优先：同等参数优先推荐国产替代（降本+供应链安全）
- 数据驱动：选型建议基于真实库存、交期、价格数据
- 兼容性优先：替代料必须pin-to-pin兼容或软件适配成本可控
- 风险提示：EOL/NRND器件必须高亮预警
"""

    async def analyze(self, goal: str) -> dict:
        """执行BOM选型分析（可复现，无随机）"""
        logger.info(f"[BOM Selector Agent] Analyzing: {goal[:60]}...")

        target_part = self._match_component(goal)
        target = await self.tools.get_component(target_part)
        if not target:
            return {
                "status": "completed",
                "summary": f"未找到目标器件 {target_part} 的参数数据",
                "recommendations": ["📋 请确认型号是否正确，或补充该器件参数"],
            }

        alt_ids = await self.tools.get_alternatives(target_part)
        alternatives = []

        for alt_id in alt_ids:
            comp = await self.tools.get_component(alt_id)
            if not comp:
                continue

            compatibility = self._check_compatibility(target, comp)

            alternatives.append({
                "part_number": alt_id,
                "manufacturer": comp["manufacturer"],
                "package": comp["package"],
                "unit_price": comp["unit_price_usd"],
                "price_diff_pct": round((comp["unit_price_usd"] - target["unit_price_usd"]) / target["unit_price_usd"] * 100, 1),
                "lead_time_days": comp["lead_time_days"],
                "stock_qty": comp["stock_qty"],
                "monthly_usage": comp["avg_monthly_usage"],
                "lifecycle": comp["lifecycle"],
                "compatibility": compatibility["level"],
                "compatibility_notes": compatibility["notes"],
                "is_domestic": comp["manufacturer"] in ("GigaDevice", "Artery Tech"),
            })

        alternatives.sort(key=lambda x: (
            0 if x["compatibility"] == "pin-to-pin" else 1,
            0 if x["is_domestic"] else 1,
            x["unit_price"],
        ))

        cost_analysis = self._cost_analysis(target, alternatives)
        recommendations = self._generate_recommendations(target_part, alternatives)

        # 提交首选替代料审批（真实动作）
        actions_taken = []
        if alternatives:
            best = alternatives[0]
            approval = await self.tools.submit_alt_approval(target_part, best["part_number"], best["compatibility_notes"])
            actions_taken.append({
                "type": "submit_alt_approval",
                "detail": f"提交替代料审批：{target_part} → {best['part_number']}（{approval.get('approval_id', '')}）",
                "target": target_part,
                "alt": best["part_number"],
                "confidence": 0.84,
            })

        return {
            "status": "completed",
            "summary": f"BOM选型分析完成：目标器件{target_part}，找到{len(alternatives)}个替代方案",
            "target_component": {
                "part_number": target_part,
                "manufacturer": target.get("manufacturer", ""),
                "category": target.get("category", ""),
                "unit_price": target.get("unit_price_usd", 0),
                "lifecycle": target.get("lifecycle", ""),
                "stock_qty": target.get("stock_qty", 0),
                "lead_time": target.get("lead_time_days", 0),
            },
            "alternatives": alternatives,
            "cost_analysis": cost_analysis,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _match_component(self, goal: str) -> str:
        """从目标匹配器件（基于已加载的种子键，无随机）"""
        goal_upper = goal.upper()
        for part_num in self.tools._components:
            if part_num.upper() in goal_upper:
                return part_num
        if "MCU" in goal_upper or "STM32" in goal_upper or "单片机" in goal:
            return "STM32F407VGT6"
        if "DC" in goal_upper or "电源" in goal or "TPS" in goal_upper:
            return "TPS63020DSJR"
        return "STM32F407VGT6"

    def _check_compatibility(self, target: dict, alt: dict) -> dict:
        """检查兼容性"""
        notes = []

        if target.get("package") == alt.get("package"):
            level = "pin-to-pin"
            notes.append(f"封装一致({alt['package']})，可直接替换")
        else:
            level = "functional"
            notes.append(f"封装不同({alt['package']} vs {target['package']})，需改板")

        if alt.get("max_freq_mhz", 0) > target.get("max_freq_mhz", 0):
            notes.append(f"主频更高({alt['max_freq_mhz']}MHz vs {target['max_freq_mhz']}MHz)，性能提升")
        elif alt.get("max_freq_mhz", 0) < target.get("max_freq_mhz", 0):
            notes.append(f"⚠️ 主频更低({alt['max_freq_mhz']}MHz)，需确认是否满足需求")

        if alt.get("ram_kb", 0) > target.get("ram_kb", 0):
            notes.append(f"RAM更大({alt['ram_kb']}KB vs {target['ram_kb']}KB)")

        if alt.get("manufacturer") in ("GigaDevice", "Artery Tech"):
            notes.append("🇨🇳 国产器件，供应链更稳定")

        return {"level": level, "notes": "; ".join(notes)}

    def _cost_analysis(self, target: dict, alternatives: list) -> dict:
        """成本分析"""
        target_price = target["unit_price_usd"]
        best_alt = min(alternatives, key=lambda x: x["unit_price"]) if alternatives else None
        savings_pct = 0
        if best_alt:
            savings_pct = round((target_price - best_alt["unit_price"]) / target_price * 100, 1)
        annual_qty = target.get("avg_monthly_usage", 0) * 12
        return {
            "target_annual_cost_usd": round(target_price * annual_qty, 0),
            "best_alternative": best_alt["part_number"] if best_alt else None,
            "best_alt_price": best_alt["unit_price"] if best_alt else 0,
            "annual_savings_usd": round((target_price - (best_alt["unit_price"] if best_alt else target_price)) * annual_qty, 0),
            "savings_pct": savings_pct,
            "annual_qty": annual_qty,
        }

    def _generate_recommendations(self, target_part: str, alternatives: list) -> list:
        """生成选型建议"""
        recs = []
        if not alternatives:
            recs.append("未找到兼容替代料，建议联系原厂确认替代方案")
            return recs

        best = alternatives[0]
        if best["is_domestic"]:
            recs.append(f"🇨🇳 推荐首选：{best['part_number']}（{best['manufacturer']}），国产pin-to-pin兼容，降本{abs(best['price_diff_pct'])}%")
        else:
            recs.append(f"推荐首选：{best['part_number']}（{best['manufacturer']}），兼容性最佳")

        if best.get("price_diff_pct", 0) < 0:
            recs.append(f"💰 成本优化：单价从${self.tools._components[target_part]['unit_price_usd']}降至${best['unit_price']}，节省{abs(best['price_diff_pct'])}%")

        for alt in alternatives:
            if alt["stock_qty"] < 10000:
                recs.append(f"⚠️ {alt['part_number']}库存偏低({alt['stock_qty']})，建议提前备货")

        recs.append("📋 建议小批量验证后批量切换，验证项：功能测试+温漂+EMC")
        return recs


bom_selector_agent = BOMSelectorAgent()
