"""LLM 客户端 —— AI原生 L2 推理层的基础设施

设计原则：
1. OpenAI 兼容协议，用已安装的 httpx 直连，不引入 openai 依赖
2. 支持双 provider：DeepSeek（主，settings.llm_*）/ 混元 Hunyuan（备，settings.hunyuan_*）
3. **绝不抛异常**：任何网络/鉴权/解析错误都返回 None，调用方据此走规则引擎兜底
4. 无 API Key 时 available=False，chat() 直接返回 None，不发任何网络请求
"""

from __future__ import annotations

import json
import logging

import httpx

from src.common.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """轻量、容错的 LLM 客户端。"""

    def __init__(self):
        # 构建可用 provider 列表：先 deepseek，后 hunyuan
        self._providers: dict[str, dict] = {}
        if settings.llm_api_key:
            self._providers["deepseek"] = {
                "base_url": settings.llm_base_url,
                "api_key": settings.llm_api_key,
                "fast_model": settings.llm_fast_model,
                "reasoning_model": settings.llm_reasoning_model,
            }
        if settings.hunyuan_api_key:
            self._providers["hunyuan"] = {
                "base_url": settings.hunyuan_base_url,
                "api_key": settings.hunyuan_api_key,
                "fast_model": settings.hunyuan_model,
                "reasoning_model": settings.hunyuan_model,
            }
        # 默认 provider：配置指定的优先；否则用第一个可用的
        self._default = settings.llm_provider if settings.llm_provider in self._providers else (
            next(iter(self._providers)) if self._providers else None
        )

    @property
    def available(self) -> bool:
        return bool(self._providers)

    @property
    def providers(self) -> list[str]:
        return list(self._providers.keys())

    def _model_for(self, provider: str, reasoning: bool = False) -> str | None:
        p = self._providers.get(provider)
        if not p:
            return None
        return p["reasoning_model"] if reasoning else p["fast_model"]

    async def chat(
        self,
        messages: list[dict],
        provider: str | None = None,
        model: str | None = None,
        reasoning: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 900,
    ) -> str | None:
        """一次聊天补全。成功返回文本，失败（含无 Key）返回 None。"""
        # 选定 provider：显式 > 默认 > 任一可用
        prov = provider or self._default
        if prov not in self._providers and self._providers:
            prov = next(iter(self._providers))
        cfg = self._providers.get(prov)
        if not cfg:
            return None

        model = model or self._model_for(prov, reasoning)
        if not model:
            return None

        url = f"{cfg['base_url'].rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001 —— 容错是核心契约
            logger.warning("LLM call failed [%s/%s]: %s", prov, model, e)
            return None

    async def generate_plan(
        self,
        agent_name: str,
        goal: str,
        analysis_context: str,
        reasoning: bool = False,
    ) -> str | None:
        """基于确定性分析结果，生成给人审批的自然语言规划（Markdown）。

        Args:
            agent_name: 路由到的 Agent 名称
            goal: 用户自然语言目标
            analysis_context: 确定性 Agent 分析产出的原始文本（作为事实锚点）
            reasoning: 是否用推理模型（deepseek-reasoner / hunyuan 对应模型）

        Returns:
            Markdown 规划文本，或 None（调用方走规则引擎兜底）
        """
        if not self.available:
            return None

        system = (
            "你是智衍 EvolvIQ 工业智能体平台的 AI 规划引擎（L2 推理层）。"
            "你的职责是把用户的自然语言目标，结合某个工业 Agent 已经算出的确定性分析结果，"
            "生成一份结构清晰、给人审批的 Markdown 规划。\n"
            "严格要求：\n"
            "1. 只能基于下方『分析结果』中的真实数据来组织规划，不得编造任何数字、物料、设备或动作。\n"
            "2. 规划应包含：目标理解、执行路径（分步骤）、预期动作、需关注的风险。\n"
            "3. 使用简洁的中文，面向工厂业务人员，不要堆砌技术术语。\n"
            "4. 输出纯 Markdown，不要使用代码块包裹。"
        )
        user = (
            f"# 目标\n{goal}\n\n"
            f"# 路由到的 Agent\n{agent_name}\n\n"
            f"# 确定性分析结果（事实锚点，必须据此规划）\n{analysis_context}\n\n"
            "请生成规划预览："
        )
        return await self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            reasoning=reasoning,
            temperature=0.3,
            max_tokens=900,
        )

    async def generate_decision_insight(
        self,
        agent_name: str,
        goal: str,
        facts: str,
        reasoning: bool = False,
    ) -> str | None:
        """执行阶段的 LLM 决策辅助（L2 推理层下沉到 Agent 执行）。

        与 generate_plan 的区别：generate_plan 面向"执行前"的规划预览；
        本方法面向"执行后"——Agent 已产出确定性事实（齐套率/健康分/缺陷/
        已自主动作/待审批动作），让 LLM 基于这些事实做决策解读、优先级排序、
        风险研判，辅助人做审批与后续决策。**绝不改写任何确定性数字与动作**。

        Args:
            agent_name: 执行的 Agent 名称
            goal: 用户目标
            facts: 确定性执行结果的事实摘要（作为唯一事实来源）
            reasoning: 是否用推理模型

        Returns:
            Markdown 决策辅助（三段：决策解读/建议优先级/风险研判），或 None（走无 AI 辅助的纯确定性结果）
        """
        if not self.available:
            return None

        system = (
            "你是智衍 EvolvIQ 工业智能体平台的 AI 决策辅助引擎（L2 推理层，执行阶段）。"
            "某个工业 Agent 已经完成执行并产出了确定性结果（下方『执行事实』），"
            "你的职责是基于这些**已发生的事实**，为工厂决策者提供简洁的决策辅助。\n"
            "严格要求：\n"
            "1. 只能引用『执行事实』中的真实数字、物料、设备、动作，"
            "**严禁编造或推算任何事实中不存在的数值**。\n"
            "2. 输出恰好三个小节，用 Markdown 二级列表：\n"
            "   **决策解读**：这些结果意味着什么（1-3 条）。\n"
            "   **建议优先级**：结合已自主执行 / 待人工审批的动作，先处理什么（1-3 条，按紧急度排序）。\n"
            "   **风险研判**：需要警惕的风险或盲点（1-2 条）。\n"
            "3. 每条一句话，面向工厂业务人员，简洁克制，不堆术语。\n"
            "4. 输出纯 Markdown，不要用代码块包裹，不要加多余标题。"
        )
        user = (
            f"# 用户目标\n{goal}\n\n"
            f"# 执行 Agent\n{agent_name}\n\n"
            f"# 执行事实（唯一事实来源，不得超出此范围编造）\n{facts}\n\n"
            "请给出决策辅助："
        )
        return await self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            reasoning=reasoning,
            temperature=0.2,
            max_tokens=700,
        )


# 全局单例
llm_client = LLMClient()
