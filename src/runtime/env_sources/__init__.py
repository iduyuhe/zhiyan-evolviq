"""环境感知第⑥路源适配器包（v30.0 α，2026-08-02 补客户声音）。

源与可信分级（F4：官方为锚，其余必筛）：
- policy            政策法规（官方发布，official）
- market            原材料行情（官方指数，official）
- benchmark         行业智能化对标（官方名录，official）
- disclosure        上市企业公告披露（研究案例·官方披露，official，平台级源）
- customer_voice    客户声音情报（招投标/行业报告/舆情，authoritative→人工审核队列）

统一经 `uns.publish_environment` 入总线；credibility 分级门见 `src/runtime/env_perception.py`。
"""

from src.runtime.env_sources.manager import env_manager  # noqa: F401
