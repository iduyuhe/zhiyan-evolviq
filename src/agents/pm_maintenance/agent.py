"""设备预测维护Agent——半导体设备智能诊断与维护建议

目标场景：SMIC晶圆厂的光刻机、刻蚀机、薄膜沉积设备等核心设备的预测维护。
能力范围：
1. 设备健康评分（基于部件寿命+传感器读数加权，可复现，非随机）
2. 关键部件寿命预测与备件预警
3. 预防维护工单建议
4. 备件采购申请

数据层：通过 PMTools 从 data/seed/pm_equipment.json 加载，可切换真实MCP(EAM/PLC)。
"""

import logging

from src.agents.pm_maintenance.tools import PMTools

logger = logging.getLogger(__name__)


class PMAgent:
    """设备预测维护Agent"""

    def __init__(self):
        self.tools = PMTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「设备预测维护Agent」，专注半导体制造设备的智能诊断与维护管理。

## 当前服务客户：中芯国际 SMIC
- 核心设备：光刻机(ASML)、刻蚀机(中微)、薄膜沉积(AMAT)
- 管理目标：设备综合效率(OEE)≥85%，非计划停机减少50%

## 核心能力
1. 设备健康评分（基于部件寿命+传感器综合评估）
2. 关键部件寿命预测（光源/真空腔/静电卡盘等）
3. 维修保养建议（基于设备数据和历史故障模式）
4. 备件更换预警（按备件采购周期提前预警）

## 工作原则
- 数据驱动：每项建议必须有设备数据支撑
- 预防为主：提前发现潜在故障，避免非计划停机
- 维修优先级：安全 > 质量 > 效率 > 成本
"""

    async def analyze(self, goal: str) -> dict:
        """分析设备维护需求"""
        logger.info(f"[PM Agent] Analyzing: {goal[:60]}...")

        all_equipments = await self.tools.get_equipment_list()
        target_ids = self._match_equipments(goal, all_equipments)

        results = []
        alerts = []
        actions_taken = []

        for eq_id in target_ids:
            profile = await self.tools.get_equipment_health(eq_id)
            if not profile:
                continue

            parts = profile.get("key_parts", [])
            sensors = profile.get("sensors", {})

            # 可复现的健康分：部件寿命加权(70%) + 传感器偏差惩罚(30%)
            health = self._compute_health(parts, sensors)

            risky_parts = [p for p in parts if p.get("risk") in ("high", "medium")]
            high_risk_parts = [p for p in parts if p.get("risk") == "high"]

            results.append({
                "equipment_id": eq_id,
                "name": profile["name"],
                "type": profile["type"],
                "vendor": profile.get("vendor", ""),
                "location": profile.get("location", ""),
                "health_score": health,
                "status": "normal" if health > 70 else "warning" if health > 50 else "critical",
                "uptime_hours": profile.get("uptime_hours", 0),
                "mtbf_hours": profile.get("mtbf_hours", 0),
                "next_pm_due": profile.get("next_pm_due", ""),
                "sensors": sensors,
                "risky_components": risky_parts,
                "recent_alerts": profile.get("recent_alerts", []),
            })

            if health < 80:
                alerts.append(f"🟠 {profile['name']} 健康评分 {health}，建议安排预防维护")
                actions_taken.append({
                    "type": "create_pm_workorder",
                    "detail": f"为 {profile['name']} 创建预防维护工单",
                    "equipment_id": eq_id,
                    "confidence": 0.82,
                })

            # 高风险部件 → 备件采购预警
            for p in high_risk_parts:
                alerts.append(
                    f"🔴 {profile['name']} 部件[{p['name']}]寿命仅剩{p['life_remaining_pct']}%，"
                    f"采购周期{p.get('replace_lead_days', 30)}天，需尽快备货"
                )
                actions_taken.append({
                    "type": "create_spare_part_order",
                    "detail": f"申请备件 {p.get('part_no', p['name'])} × 1（{profile['name']}）",
                    "part_no": p.get("part_no", ""),
                    "qty": 1,
                    "lead_days": p.get("replace_lead_days", 30),
                    "confidence": 0.88,
                })

        summary = f"检查了{len(results)}台核心设备，发现{len(alerts)}项维护需求，生成{len(actions_taken)}个建议动作"
        return {
            "status": "completed",
            "summary": summary,
            "equipments": results,
            "alerts": alerts,
            "actions_taken": actions_taken,
        }

    def _compute_health(self, parts: list[dict], sensors: dict) -> float:
        """可复现的设备健康评分：部件寿命均值(70%权重) + 传感器偏差惩罚(30%权重)"""
        if not parts:
            return 100.0
        avg_life = sum(p.get("life_remaining_pct", 100) for p in parts) / len(parts)

        # 传感器偏差惩罚：刻蚀速率偏差、振动等异常项
        penalty = 0.0
        dev = sensors.get("etch_rate_deviation_pct", 0)
        if dev:
            penalty += min(abs(dev) * 2, 15)
        vib = sensors.get("vibration_mm_s", 0)
        if vib and vib > 0.5:
            penalty += min((vib - 0.5) * 10, 10)

        health = avg_life * 0.7 + (100 - penalty) * 0.3
        return round(max(0, min(100, health)), 1)

    def _match_equipments(self, goal: str, all_equipments: list[dict]) -> list[str]:
        """从目标文本匹配设备"""
        all_ids = [eq["equipment_id"] for eq in all_equipments]
        match_map = {
            "光刻": ["scanner_1"],
            "scanner": ["scanner_1"],
            "刻蚀": ["etcher_1"],
            "etcher": ["etcher_1"],
            "沉积": ["deposition_1"],
            "薄膜": ["deposition_1"],
        }
        for keyword, ids in match_map.items():
            if keyword in goal.lower():
                return [i for i in ids if i in all_ids]
        # 默认返回全部设备
        return all_ids


pm_agent = PMAgent()
