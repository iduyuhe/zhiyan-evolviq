"""质量追溯Agent——晶圆质量问题根因追溯

目标场景：SMIC晶圆厂客诉或产线异常时，从问题晶圆反向追溯根因。
能力范围：
1. 客诉晶圆批次追溯（从客诉→批次→工艺→设备→参数）
2. 缺陷模式识别（根据缺陷特征匹配已知故障模式）
3. 根因定位（基于知识图谱推理）
4. 纠正措施建议（基于历史成功案例）

数据层：通过 QualityTraceTools 从 data/seed/quality_trace.json 加载，可切换真实MCP(MES/LIMS)。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.quality_trace.tools import QualityTraceTools

logger = logging.getLogger(__name__)


class QualityTraceAgent(BaseAgent):
    """质量追溯Agent"""

    name = "quality_trace"
    description = "客诉溯源、缺陷模式识别、根因分析与 CAPA 建议"

    def __init__(self):
        self.tools = QualityTraceTools()
        self.system_prompt = self._build_prompt()

    async def analyze(self, goal: str) -> dict:
        """统一入口：等价于 `trace(goal)`（向后兼容保留 trace）。"""
        return await self.trace(goal)

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「质量追溯Agent」，专注半导体晶圆制造的质量问题根因追溯。

## 当前服务客户：中芯国际 SMIC
- 产品：28nm及以上逻辑工艺
- 质量目标：客诉响应＜24h，根因定位准确率≥90%
- 核心能力：从客诉到设备/工艺/参数的端到端追溯

## 核心能力
1. 客诉→批次→工艺→设备→参数的逐级追溯
2. 缺陷模式识别与相似案例匹配
3. 根因推理（基于缺陷分布、设备日志、工艺参数）
4. 纠正与预防措施(CAPA)建议

## 工作原则
- 根因导向：不只找到直接原因，还要挖掘系统原因
- 数据链完整：每步追溯必须有数据支撑
- 时效优先：24小时内完成首轮根因分析
"""

    async def trace(self, query: str) -> dict:
        """执行质量追溯（可复现，无随机）"""
        logger.info(f"[QualityTrace] Tracing: {query[:60]}...")

        matched_case = await self.tools.search_cases(query)
        if not matched_case:
            # 未匹配历史案例：开新追溯工单，给出结构化的待查路径
            ticket = await self.tools.open_investigation_ticket(query)
            return {
                "status": "completed",
                "summary": f"未匹配历史案例，已创建新追溯工单 {ticket.get('ticket_id', 'N/A')}",
                "ticket_id": ticket.get("ticket_id"),
                "trace_path": [
                    {"step": 1, "from": "客诉/异常", "to": "批次追溯", "finding": "按晶圆批号查询MES批次记录"},
                    {"step": 2, "from": "批次", "to": "工艺路径", "finding": "还原光刻→刻蚀→沉积→测试工艺链"},
                    {"step": 3, "from": "工艺", "to": "设备匹配", "finding": "按缺陷特征+时间戳匹配嫌疑设备"},
                    {"step": 4, "from": "设备", "to": "参数分析", "finding": "拉取异常时段工艺参数曲线"},
                    {"step": 5, "from": "参数", "to": "根因结论", "finding": "综合判定，必要时触发FA分析"},
                ],
                "suspected_equipments": [],
                "root_cause": "待数据齐备后生成首轮根因假设",
                "fix_actions": ["待根因确认后生成CAPA"],
                "historical_similar": 0,
                "actions_taken": [
                    {
                        "type": "open_investigation_ticket",
                        "detail": f"创建追溯工单 {ticket.get('ticket_id', '')}",
                        "confidence": 0.7,
                    }
                ],
            }

        # 构建可追溯路径（基于案例结构化字段）
        trace_path = [
            {"step": 1, "from": "客诉", "to": "批次信息", "finding": f"问题批次: {matched_case['affected_qty']}片晶圆（{matched_case['found_stage']}）"},
            {"step": 2, "from": "批次", "to": "工艺追溯", "finding": "涉及工艺: 光刻→刻蚀→沉积"},
            {"step": 3, "from": "工艺", "to": "设备追溯", "finding": f"嫌疑设备: {matched_case['suspected_equipments'][0]['name']}(匹配度{matched_case['suspected_equipments'][0]['match_score']})"},
            {"step": 4, "from": "设备", "to": "根因定位", "finding": matched_case["root_cause"]},
        ]

        # 生成CAPA任务（真实动作）
        capa = await self.tools.create_capa(matched_case["id"], matched_case["fix_actions"])

        return {
            "status": "completed",
            "summary": f"质量追溯完成：{matched_case['issue']}（{matched_case['id']}，{matched_case['severity']}），根因已定位",
            "id": matched_case["id"],
            "product": matched_case["product"],
            "issue": matched_case["issue"],
            "severity": matched_case["severity"],
            "affected_qty": matched_case["affected_qty"],
            "found_stage": matched_case["found_stage"],
            "timeline": matched_case.get("timeline", {}),
            "trace_path": trace_path,
            "suspected_equipments": matched_case["suspected_equipments"],
            "root_cause": matched_case["root_cause"],
            "fix_actions": matched_case["fix_actions"],
            "historical_similar": matched_case["historical_similar"],
            "capa_task_id": capa.get("task_id"),
            "actions_taken": [
                {
                    "type": "create_capa",
                    "detail": f"针对 {matched_case['id']} 生成CAPA任务（{capa.get('task_id', '')}）",
                    "case_id": matched_case["id"],
                    "confidence": 0.9,
                }
            ],
        }


quality_trace_agent = QualityTraceAgent()
