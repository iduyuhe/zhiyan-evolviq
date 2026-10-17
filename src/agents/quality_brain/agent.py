"""质量决策脑 QualityBrain —— 质量域统一编排层（强化 P0）

把孤立的质量子 Agent 聚合成「实时事件驱动的质量决策脑」：
- analyze(goal)      : 按需聚合 追溯/判图/良率/合规 四子 Agent，输出五类质量干预
- ingest_event(event): 接收 UNS 质量事件（aoi/spc/complaint/equipment/batch），映射为干预建议
- 人留终审          : 所有 action 统一 requires_human_approval=true，质量决策脑不代签放行
- 韧性降级          : 子 Agent 不可达时延迟 import + 返回降级占位（沿用全栈铁律）

五类干预（与 APS 造船感知五类干预对齐的「质量版」）：
① 缺陷预警 ② 误报抑制 ③ 良率保卫 ④ 追溯触发 ⑤ CAPA 闭环
"""

import logging

from src.agents.base import BaseAgent
from src.agents.quality_brain.tools import (
    EVENT_TO_INTERVENTIONS,
    INTERVENTION_CATALOG,
    catalog_zh,
    intervention_order,
)

logger = logging.getLogger(__name__)


class QualityBrainAgent(BaseAgent):
    """质量决策脑——质量域统一编排层。"""

    name = "quality_brain"
    description = "质量决策脑：统筹追溯/判图/良率/合规四子Agent，输出五类质量干预（人留终审）"

    def __init__(self):
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return (
            "# 角色定义\n你是智衍(EvolvIQ)平台的「质量决策脑 QualityBrain」，质量域的统一编排层。\n\n"
            "## 核心职责\n统筹质量域四个子 Agent——质量追溯 / AOI 判图 / 良率分析 / 质量合规，"
            "把它们的发现聚合为统一的质量干预决策。\n\n"
            "## 五类干预\n1. 缺陷预警：基于缺陷趋势/分布提前预警\n"
            "2. 误报抑制：降低 AOI 等检测误报，避免无效复判\n"
            "3. 良率保卫：盯住良率缺口与低良率设备\n"
            "4. 追溯触发：客诉/异常时反向追溯根因\n"
            "5. CAPA 闭环：把纠正措施建议形成可闭环任务\n\n"
            "## 工作原则\n- 人留终审：质量决策脑只输出建议，所有动作需人工确认，不代签放行\n"
            "- 数据驱动：每条干预须有子 Agent 数据/事实支撑\n"
            "- 实时优先：支持从 UNS 质量事件直接触发干预\n"
        )

    # ---------- 主入口 ----------
    async def analyze(self, goal: str) -> dict:
        """聚合四子 Agent，输出五类干预（人留终审）。"""
        logger.info(f"[QualityBrain] Analyzing: {goal[:60]}...")
        sub = await self._aggregate(goal)
        interventions = self._build_interventions(sub, goal)
        actions = self._gate(interventions)
        summary = self._summarize(interventions, sub)
        return {
            "status": "completed",
            "summary": summary,
            "five_interventions": interventions,
            "sub_agent_findings": sub,
            "actions_taken": actions,
            "human_approval_required": True,
        }

    # ---------- 事件入口（UNS 质量事件） ----------
    async def ingest_event(self, event: dict) -> dict:
        """接收一条 UNS 质量事件，映射为质量干预建议。

        event 约定: {"event_type": "aoi"|"spc"|"complaint"|"equipment"|"batch",
                      "payload": {...}, "channel": str, "tenant_id": str}
        返回结构与人留终审闸门同 analyze()。
        """
        etype = (event or {}).get("event_type", "unknown")
        cats = EVENT_TO_INTERVENTIONS.get(etype, ["defect_forecast"])
        interventions = []
        for c in cats:
            interventions.append({
                "type": c,
                "label": catalog_zh(c),
                "detail": f"UNS 事件[{etype}]触发『{catalog_zh(c)}』干预，需人工确认后执行",
                "source": "uns_event",
                "event_type": etype,
                "severity": "medium",
                "confidence": 0.82,
            })
        interventions = self._fill_missing(interventions)
        actions = self._gate(interventions)
        return {
            "status": "completed",
            "event_type": etype,
            "summary": f"UNS 质量事件[{etype}]已映射为 {len([a for a in actions])} 项质量干预（待人工确认）",
            "five_interventions": interventions,
            "actions_taken": actions,
            "human_approval_required": True,
        }

    # ---------- 内部聚合 ----------
    async def _aggregate(self, goal: str) -> dict:
        """延迟 import 四子 Agent 单例并聚合；任一不可达即降级占位。"""
        sub: dict = {}

        async def safe(call, key):
            try:
                return await call()
            except Exception as e:  # noqa: BLE001 - 韧性降级：子Agent不可用不影响主脑
                logger.warning("[QualityBrain] 子Agent[%s]降级: %s", key, e)
                return {"status": "degraded", "reason": str(e)[:120]}

        async def trace():
            from src.agents.quality_trace.agent import quality_trace_agent
            return await quality_trace_agent.trace(goal)

        async def aoi():
            from src.agents.aoi_judge.agent import aoi_agent
            return await aoi_agent.analyze(goal)

        async def yld():
            from src.agents.yield_analysis.agent import yield_agent
            return await yield_agent.analyze(goal)

        async def compliance():
            # mode="research" 仅做只读推演，不写租户作用域 CAPA（人留终审更纯净）
            from src.agents.compliance_q.agent import compliance_agent
            return await compliance_agent.analyze(goal, mode="research")

        sub["trace"] = await safe(trace, "quality_trace")
        sub["aoi"] = await safe(aoi, "aoi_judge")
        sub["yield"] = await safe(yld, "yield_analysis")
        sub["compliance"] = await safe(compliance, "compliance_q")
        return sub

    @staticmethod
    def _mk(type_, label, detail, source, sev, conf, degraded) -> dict:
        """构造一条干预；若来源子 Agent 降级，则降级为零置信占位（避免误报动作）。"""
        if degraded:
            return {
                "type": type_,
                "label": label,
                "detail": f"{detail}（来源子Agent降级，待数据恢复后复核）",
                "source_sub_agent": source,
                "severity": "low",
                "confidence": 0.0,
            }
        return {
            "type": type_,
            "label": label,
            "detail": detail,
            "source_sub_agent": source,
            "severity": sev,
            "confidence": conf,
        }

    def _build_interventions(self, sub: dict, goal: str) -> list:
        """把四子 Agent 的发现聚合成五类干预；来源降级则统一降级占位。"""
        y = sub.get("yield", {})
        a = sub.get("aoi", {})
        t = sub.get("trace", {})
        c = sub.get("compliance", {})
        y_deg = y.get("status") == "degraded"
        a_deg = a.get("status") == "degraded"
        t_deg = t.get("status") == "degraded"
        c_deg = c.get("status") == "degraded"
        out = []
        # ① 缺陷预警
        defects = y.get("defects") or []
        rising = [d for d in defects if d.get("trend") == "上升中"]
        out.append(self._mk(
            "defect_forecast", INTERVENTION_CATALOG["defect_forecast"],
            (f"检测到 {len(rising)} 类缺陷呈上升趋势" if rising else "当前缺陷趋势平稳，无上升预警"),
            "yield_analysis",
            "high" if rising else "low", 0.8, y_deg,
        ))
        # ② 误报抑制
        far = a.get("false_alarm_rate")
        out.append(self._mk(
            "false_alarm_suppression", INTERVENTION_CATALOG["false_alarm_suppression"],
            (f"AOI 误报率 {far}%，建议阈值优化以降低无效复判" if far else "AOI 误报率数据缺失"),
            "aoi_judge",
            "medium" if (far and far >= 20) else "low", 0.78, a_deg,
        ))
        # ③ 良率保卫
        gap = y.get("gap")
        out.append(self._mk(
            "yield_defense", INTERVENTION_CATALOG["yield_defense"],
            (f"良率缺口 {gap} 个百分点，建议优先治理 top 缺陷" if gap and gap > 0 else "良率达标，无需干预"),
            "yield_analysis",
            "high" if (gap and gap > 0) else "low", 0.8, y_deg,
        ))
        # ④ 追溯触发
        out.append(self._mk(
            "trace_trigger", INTERVENTION_CATALOG["trace_trigger"],
            (f"追溯完成：{t.get('root_cause', '根因待定')}" if t.get("status") == "completed" else "暂无客诉追溯触发"),
            "quality_trace",
            "high" if t.get("severity") in ("critical", "high") else "low", 0.85, t_deg,
        ))
        # ⑤ CAPA 闭环
        capa = c.get("capa_tasks") or c.get("actions_taken") or []
        # 仅保留 create_capa 类动作，避免把无关动作误判为 CAPA
        capa = [x for x in capa if "capa" in str(x.get("type", "")).lower()] if isinstance(capa, list) else []
        out.append(self._mk(
            "capa_loop", INTERVENTION_CATALOG["capa_loop"],
            (f"已生成 {len(capa)} 项 CAPA 任务建议，待人工确认闭环" if capa else "暂无 CAPA 建议"),
            "compliance_q",
            "medium", 0.8, c_deg,
        ))
        return out

    def _fill_missing(self, interventions: list) -> list:
        """保证五类干预齐全（事件入口可能只触发部分类）。"""
        present = {i["type"] for i in interventions}
        for k in intervention_order():
            if k not in present:
                interventions.append({
                    "type": k,
                    "label": INTERVENTION_CATALOG[k],
                    "detail": "本次事件未触发该干预",
                    "source_sub_agent": "quality_brain",
                    "severity": "low",
                    "confidence": 0.0,
                })
        order = intervention_order()
        return sorted(interventions, key=lambda x: order.index(x["type"]))

    def _gate(self, interventions: list) -> list:
        """人留终审闸门：所有 action 统一 requires_human_approval=true，不代签。"""
        actions = []
        for iv in interventions:
            # 未触发的干预（severity=low 且 confidence=0）不生成动作
            if iv.get("severity") == "low" and iv.get("confidence", 1) == 0.0:
                continue
            actions.append({
                "type": iv["type"],
                "detail": iv["detail"],
                "requires_human_approval": True,
                "auto_executable": False,
                "status": "pending_approval",
                "confidence": iv.get("confidence", 0.8),
            })
        return actions

    def _summarize(self, interventions: list, sub: dict) -> str:
        active = [i for i in interventions if i.get("confidence", 0) > 0]
        status_str = "/".join(f"{k}:{sub.get(k, {}).get('status', '?')}" for k in sub)
        return (
            f"质量决策脑完成聚合：四子 Agent 状态 {status_str}；"
            f"{len(active)} 项有效干预，全部需人工确认。"
        )


quality_brain_agent = QualityBrainAgent()
