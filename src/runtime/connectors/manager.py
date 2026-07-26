"""社交通道管理器（v29.9）—— 进程级单例，聚合企微/钉钉/邮件连接器。

职责：
- 统一构造三个连接器（按 env 配置判定 enabled）。
- 对外暴露连接器清单、单连接器连通性测试、邮件手动拉取。
- 韧性：构造失败静默降级，绝不阻断启动。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SocialConnectorManager:
    def __init__(self) -> None:
        self._connectors: dict[str, Any] = {}
        self._init()

    def _init(self) -> None:
        # 延迟 import：避免 connectors 包在沙箱缺 cryptography 时报 ImportError
        try:
            from src.runtime.connectors.wecom_ingest import WeComConnector
            from src.runtime.connectors.dingtalk_ingest import DingTalkConnector
            from src.runtime.connectors.email_ingest import EmailConnector

            for cls in (WeComConnector, DingTalkConnector, EmailConnector):
                try:
                    inst = cls()
                    self._connectors[inst.name] = inst
                except Exception as e:
                    logger.warning(f"⚠️ 社交连接器 {cls.__name__} 初始化失败（跳过）：{e}")
        except Exception as e:
            logger.warning(f"⚠️ 社交通道包加载失败（不破管）：{e}")

    def list(self) -> list[dict]:
        return [c.status() for c in self._connectors.values()]

    def get(self, name: str) -> Any | None:
        return self._connectors.get(name)

    async def test(self, name: str) -> dict:
        c = self._connectors.get(name)
        if c is None:
            return {"name": name, "ok": False, "detail": "未知或未配置的连接器"}
        try:
            return await c.test_connection()
        except Exception as e:
            return {"name": name, "ok": False, "detail": str(e)}

    async def pull_email(self, limit: int = 20) -> dict:
        c = self._connectors.get("email")
        if c is None:
            return {"pulled": 0, "published": 0, "sensitive": 0, "detail": "邮件连接器未配置"}
        return await c.pull(limit=limit)

    async def test_all(self) -> dict:
        out = {}
        for name in self._connectors:
            out[name] = await self.test(name)
        return out


# 进程级单例
manager = SocialConnectorManager()
