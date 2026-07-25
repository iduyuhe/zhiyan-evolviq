"""P2-3 LLM 自反思——复盘失败案例，生成候选 system prompt（含启发式兜底）。

调用 LLM 客户端复盘近期失败案例，产出修订后的完整 system prompt + 变更理由。
LLM 不可用（无 Key / 网络失败）时，回退到启发式：在原文后追加「失败模式警示」附录。
无论哪种来源，产出一律进入 status=proposed，等人工审批（绝不自动应用）。
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass

from src.common import llm_client as _llm_mod
from src.runtime.evolution.failure_store import FailureCase, failure_summary

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    proposed_prompt: str
    rationale: str
    source: str  # llm / heuristic / none


_SYSTEM = (
    "你是智衍 EvolvIQ 工业智能体平台的 Prompt 自优化引擎（自进化层 P2）。\n"
    "任务：基于某工业 Agent 近期被人类驳回/纠正的失败案例，修订它的 system prompt，"
    "使其在未来减少同类错误。\n"
    "严格要求：\n"
    "1. 保持原有角色定位、能力边界与「人在回路」原则不变，只做针对性增强。\n"
    "2. 不编造任何业务数字、物料、设备；只调整指令与约束。\n"
    "3. 输出格式：先给出修订后的【完整 system prompt】，用 <PROMPT> 和 </PROMPT> 包裹；"
    "随后给出【变更理由】（2-4 条）。\n"
    "4. 若失败案例不足以支撑修订，输出与原 prompt 一致的版本并在理由中说明。"
)

_PROMPT_RE = re.compile(r"<PROMPT>(.*?)</PROMPT>", re.DOTALL)


class LLMReflectionService:
    async def reflect(
        self, agent: str, failure_cases: list[FailureCase], current_prompt: str,
    ) -> ReflectionResult:
        if not failure_cases:
            return ReflectionResult(
                proposed_prompt=current_prompt,
                rationale="未采集到失败案例，保持当前 prompt 不变。",
                source="none",
            )

        user = (
            f"# Agent\n{agent}\n\n"
            f"# 当前 system prompt\n{current_prompt or '(Agent 未暴露 system_prompt 属性)'}\n\n"
            f"# 近期失败案例（人类驳回/纠正，按出现频次）\n{failure_summary(failure_cases)}\n\n"
            "请输出修订后的完整 prompt 与变更理由："
        )

        if _llm_mod.llm_client.available:
            text = await _llm_mod.llm_client.chat(
                [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
                reasoning=True, temperature=0.3, max_tokens=1600,
            )
            if text:
                m = _PROMPT_RE.search(text)
                if m:
                    return ReflectionResult(
                        proposed_prompt=m.group(1).strip(),
                        rationale=(text[m.end():].strip() or "(模型未单独给出理由)"),
                        source="llm",
                    )
                return ReflectionResult(
                    proposed_prompt=text.strip(),
                    rationale="(未分离 PROMPT 标记，直接采用模型输出)",
                    source="llm",
                )
            # LLM 调用返回 None（网络/鉴权失败）→ 启发式兜底
            logger.warning("⚠️ LLM 复盘返回空，回退启发式附录")

        return ReflectionResult(
            proposed_prompt=self._heuristic(current_prompt, failure_cases),
            rationale="LLM 不可用（无 Key / 调用失败），使用启发式附录（基于失败模式追加约束提示）。",
            source="heuristic",
        )

    def _heuristic(self, current_prompt: str, cases: list[FailureCase]) -> str:
        cnt = Counter(c.action_type or "未知动作" for c in cases)
        top = "、".join(f"{k}({v})" for k, v in cnt.most_common(3))
        appendix = (
            "\n\n## ⚠️ 自进化提示附录（基于人类反馈自动增补，待人工审核）\n"
            f"- 历史复核中，以下动作类型被人类驳回较多：{top}。请在执行此类动作前加强自检与事实核验。\n"
            "- 任何超出授权边界或不确定结论，必须显式交由人工确认，不得自行推断。\n"
        )
        return (current_prompt or "") + appendix


# 全局单例
reflection = LLMReflectionService()
