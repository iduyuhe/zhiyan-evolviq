"""Agent 统一基类与契约（BaseAgent）

智衍平台的所有工业 Agent 都遵循同一个最小契约：

    async def analyze(self, goal: str) -> dict

- 入参 `goal`：自然语言目标 / 查询文本。
- 返回 `dict`：结构化结果，至少包含可展示的 `status` / `summary` 等字段；
  路由层会在返回值上补写 `result["agent"] = <agent_name>`。

设计目标：
1. 社区贡献者只需实现 `analyze(goal)` 一个方法即可接入路由，无需了解内部差异。
2. 历史上个别 Agent 使用了不同的入口方法名（如 supply_chain 的
   `analyze_goal`+`execute`、quality_trace 的 `trace`）——这些方法保留向后兼容，
   同时各自补一个 `analyze()` 适配器统一对外。
3. 通过 `@abstractmethod` 在实例化时强制约束契约，避免"漏实现"。

写一个新 Agent 的最小骨架：

    from src.agents.base import BaseAgent

    class MyAgent(BaseAgent):
        name = "my_agent"
        description = "一句话描述这个 Agent 干什么"

        async def analyze(self, goal: str) -> dict:
            # ... 你的逻辑（查询→分析→建议）...
            return {"status": "completed", "summary": "..."}

    my_agent = MyAgent()   # 导出单例，供路由注册
"""

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """所有工业 Agent 的统一基类。

    子类必须：
      - 设置类属性 `name`（与路由注册键一致，如 "supply_chain"）。
      - 实现 `async def analyze(self, goal: str) -> dict`。
    """

    #: 路由注册键，子类必须覆盖（如 "supply_chain"）
    name: str = "base"
    #: 一句话能力描述，用于文档 / 能力清单展示
    description: str = ""

    @abstractmethod
    async def analyze(self, goal: str) -> dict:
        """分析目标并返回结构化结果。

        Args:
            goal: 自然语言目标 / 查询文本。

        Returns:
            结构化结果字典，建议至少包含 `status` 与 `summary`。
        """
        raise NotImplementedError

    async def recall(self, goal: str, tenant_id: str = "default", limit: int = 5) -> dict:
        """经验记忆召回（P0 记忆闭环）。

        让 Agent 在 analyze() 内能读回历史经验（跨 Agent 的 Insight 节点），
        实现"推理带记忆"。默认实现安全降级：图谱不可用时返回空，绝不阻断推理。
        Agent 可在 analyze() 内主动调用，例如：

            mem = await self.recall(goal)
            if mem["insights"]:
                # 把 mem["insights"] 作为上下文融入分析
                ...

        Returns:
            {"insights": [str, ...], "entities": [dict, ...]}
        """
        try:
            from src.runtime.memory import recall as _recall
            return await _recall(goal, tenant_id=tenant_id, limit=limit)
        except Exception:
            return {"insights": [], "entities": []}

    async def twin_context(self, tenant_id: str = "default") -> dict:
        """孪生体实时状态上下文（全息孪生社会）。

        返回各 holon 孪生体最新状态快照，供 analyze() 内融合实时镜像。
        安全降级：registry 不可用时返回空，绝不阻断推理。
        """
        try:
            from src.runtime.data_sources import registry as ds_registry
            return ds_registry.all_twin_states(tenant_id)
        except Exception:
            return {}

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"<{self.__class__.__name__} name={self.name!r}>"
