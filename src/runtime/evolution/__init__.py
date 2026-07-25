"""P2 自进化层——让平台具备"自我进化"能力（版本化 + 人工审批门）。

子模块：
- failure_store      P2-1 失败案例采集（从经验库/效果指标派生）
- prompt_versions    P2-2 Prompt 版本化管理（propose/approve/apply/rollback + 热替换）
- reflection         P2-3 LLM 自反思（复盘失败案例 → 候选 prompt，含启发式兜底）
- kg_facts           P2-4 RAG 知识自更新（事实提议 → 审批 → upsert 图谱）
- preference_learning P2-5 在线偏好学习 lite（滚动批准率 → 校准信号）

设计铁律：自进化**绝不自动应用**任何 prompt/事实变更，必须人工 approve；
且仅调整指令/约束/阈值，绝不改写业务数字（事实锚点）。
"""

from src.runtime.evolution.failure_store import FailureCase, collect_failure_cases, failure_summary
from src.runtime.evolution.prompt_versions import prompt_versions
from src.runtime.evolution.reflection import reflection, ReflectionResult
from src.runtime.evolution.kg_facts import kg_facts
from src.runtime.evolution.preference_learning import preference_calibration

__all__ = [
    "FailureCase", "collect_failure_cases", "failure_summary",
    "prompt_versions", "reflection", "ReflectionResult",
    "kg_facts", "preference_calibration",
]
