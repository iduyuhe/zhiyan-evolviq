"""P2-3 LLM ��反思——复盘失败案例 + 广样本（成功/后果/KG）生成候选 system prompt（含启发式兜底）。

调用 LLM 客户端复盘近期失败案例 + 成功案例 + 后果校验记录 + 已验证 KG 事实，
产出修订后的完整 system prompt + 变更理由。
LLM 不可用（无 Key / 网络失败）时，回退到启发式：在原文后追加「失败模式警示」附录。
无论哪种来源，产出一律进入 status=proposed，等人工审批（绝不自动应用）。

v23.0 广样本扩展：从原来的仅 failure_cases 扩大到含 success_cases / consequence_cases / kg_validated，
使反思有更全面的经验养料。
"""

from __future__ import annotations

import json
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

_SYSTEM_BROAD = (
    "你是智衍 EvolvIQ 工业智能体平台的 Prompt 自优化引擎（自进化层 P2 · 广样本模式）。\n"
    "任务：基于某工业 Agent 的全量经验反馈（失败案例 + 成功案例 + 执行后果校验 + KG 已验证知识），"
    "系统性地修订它的 system prompt，使其更鲁棒、更精确。\n"
    "严格要求：\n"
    "1. 保持原有角色定位、能力边界与「人在回路」原则不变。\n"
    "2. 从多条数据中提炼模式：哪些指令会导致驳回？哪些决策被后果验证为正确？\n"
    "3. 不编造任何业务数字、物料、设备；只调整指令与约束。\n"
    "4. 输出格式：先给出修订后的【完整 system prompt】，用 <PROMPT> 和 </PROMPT> 包裹；"
    "随后给出【变更理由】（2-4 条说明基于哪些数据）。\n"
    "5. 若数据不足以支撑修订，输出与原 prompt 一致的版本并在理由中说明。"
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

    # ---------- v23.0 广样本反思：融合多源经验养料 ----------

    async def reflect_broad(
        self,
        agent: str,
        current_prompt: str,
        failure_cases: list[FailureCase] | None = None,
        success_cases: list[dict] | None = None,
        consequence_cases: list[dict] | None = None,
        kg_validated: list[dict] | None = None,
    ) -> ReflectionResult:
        """广样本反思：从失败、成功、后果校验、KG 验证四个维度采集经验养料。"""
        failure_cases = failure_cases or []
        success_cases = success_cases or []
        consequence_cases = consequence_cases or []
        kg_validated = kg_validated or []

        total_samples = len(failure_cases) + len(success_cases) + len(consequence_cases) + len(kg_validated)
        if total_samples == 0:
            return ReflectionResult(
                proposed_prompt=current_prompt,
                rationale="未采集到任何经验样本，保持当前 prompt 不变。",
                source="none",
            )

        # 组装用户消息（含四个维度）
        parts = [f"# Agent\n{agent}\n\n", f"# 当前 system prompt\n{current_prompt or '(未暴露)'}\n"]

        parts.append(f"# 失败案例（人类驳回，{len(failure_cases)} 条）\n")
        if failure_cases:
            parts.append(failure_summary(failure_cases)[:1000])
        else:
            parts.append("(无)")

        parts.append(f"\n\n# 成功案例（人类采纳，{len(success_cases)} 条）\n")
        if success_cases:
            for s in success_cases[:10]:
                act = s.get("action_type", "?")
                ctx = s.get("context", "")[:120]
                parts.append(f"- action={act} | context={ctx}\n")
        else:
            parts.append("(无)")

        parts.append(f"\n# 后果校验记录（{len(consequence_cases)} 条）\n")
        if consequence_cases:
            for c in consequence_cases[:10]:
                aid = c.get("action_id", "?")
                mt = "match" if c.get("match") else "mismatch"
                parts.append(f"- action={aid} | {mt} | detail={json.dumps(c.get('match_detail', {}), ensure_ascii=False)[:100]}\n")
        else:
            parts.append("(无)")

        parts.append(f"\n# KG 已验证事实（{len(kg_validated)} 条）\n")
        if kg_validated:
            for k in kg_validated[:10]:
                parts.append(f"- {k.get('subject', '?')} {k.get('predicate', '?')} {k.get('object_val', '?')} (confidence={k.get('confidence', 0)})\n")
        else:
            parts.append("(无)")

        parts.append("\n请基于以上全量数据输出修订后的完整 prompt 与变更理由（说明基于哪些数据做调整）。")

        user = "".join(parts)

        if _llm_mod.llm_client.available:
            text = await _llm_mod.llm_client.chat(
                [{"role": "system", "content": _SYSTEM_BROAD}, {"role": "user", "content": user}],
                reasoning=True, temperature=0.3, max_tokens=2000,
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

        # LLM 不可用 → 启发式
        appendix_parts = []
        if failure_cases:
            cnt = Counter(c.action_type or "未知" for c in failure_cases)
            appendix_parts.append(f"- 历史驳回较多：{', '.join(f'{k}({v})' for k, v in cnt.most_common(3))}。")
        if consequence_cases:
            mismatches = sum(1 for c in consequence_cases if not c.get("match"))
            appendix_parts.append(f"- 执行后果校验：{mismatches} 条��匹配（共 {len(consequence_cases)} 条）。")
        if kg_validated:
            appendix_parts.append(f"- KG 已验证事实 {len(kg_validated)} 条可作为决策依据。")

        appendix = (
            "\n\n## ⚠️ 自进化广样本附录（基于全量经验自动增补，待人工审核）\n"
            + "\n".join(appendix_parts) +
            "\n- 任何超出授权边界或不确定结论，必须显式交由人工确认，不得自行推断。\n"
        )
        return ReflectionResult(
            proposed_prompt=(current_prompt or "") + appendix,
            rationale="LLM 不可用，使用基于广样本的启发式附录。",
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
