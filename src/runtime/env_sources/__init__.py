"""环境感知第⑥路源适配器包（v30.0 α）。

三类首批官方源（F4：官方为锚）：
- policy    政策法规（官方发布）
- market    原材料行情（官方指数）
- benchmark 行业智能化对标（官方名录，G5 轨道一）

统一经 `uns.publish_environment` 入总线；credibility 分级门见 `src/runtime/env_perception.py`。
"""

from src.runtime.env_sources.manager import env_manager  # noqa: F401
