"""环境感知源管理器（v30.0 α）—— 进程级单例，聚合三类官方源。

职责：
- 统一构造三个源适配器（政策/行情/对标，均 official 定级）。
- 对外暴露源清单、连通性测试、手动拉取（单源/全部）。
- 韧性：构造失败静默降级，绝不阻断启动。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EnvSourceManager:
    def __init__(self) -> None:
        self._sources: dict[str, Any] = {}
        self._init()

    def _init(self) -> None:
        try:
            from src.runtime.env_sources.policy_source import PolicySource
            from src.runtime.env_sources.market_source import MarketSource
            from src.runtime.env_sources.benchmark_source import BenchmarkSource
            from src.runtime.env_sources.disclosure_source import DisclosureSource

            for cls in (PolicySource, MarketSource, BenchmarkSource, DisclosureSource):
                try:
                    inst = cls()
                    self._sources[inst.name] = inst
                except Exception as e:
                    logger.warning(f"⚠️ 环境源 {cls.__name__} 初始化失败（跳过）：{e}")
        except Exception as e:
            logger.warning(f"⚠️ 环境感知源包加载失败（不破管）：{e}")

    def list(self) -> list[dict]:
        return [s.status() for s in self._sources.values()]

    def get(self, name: str) -> Any | None:
        return self._sources.get(name)

    async def test(self, name: str) -> dict:
        s = self._sources.get(name)
        if s is None:
            return {"name": name, "ok": False, "detail": "未知环境源"}
        try:
            return await s.test_connection()
        except Exception as e:
            return {"name": name, "ok": False, "detail": str(e)}

    async def pull(self, name: str, limit: int = 10) -> dict:
        s = self._sources.get(name)
        if s is None:
            return {"source": name, "pulled": 0, "published": 0, "detail": "未知环境源"}
        try:
            return await s.pull(limit=limit)
        except Exception as e:
            return {"source": name, "pulled": 0, "published": 0, "detail": str(e)}

    async def pull_all(self, limit: int = 10) -> dict:
        out = {}
        for name in self._sources:
            out[name] = await self.pull(name, limit=limit)
        return out

    async def test_all(self) -> dict:
        out = {}
        for name in self._sources:
            out[name] = await self.test(name)
        return out


# 进程级单例
env_manager = EnvSourceManager()
