"""社交通道接入基类（v29.9）

统一契约：
- enabled：连接器是否配置就绪（token/secret 等关键项非空）
- test_connection()：连通性 / token 校验探测，返回 {ok, latency_ms, detail, mode}
- publish(text, entities, source, confidence)：经隐性捕获进 UNS social 路（抽取即锚定）

所有子类必须遵守全局韧性降级铁律：异常静默吞掉、不阻断上游。
"""

from __future__ import annotations

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SocialConnectorBase:
    """社交通道接入基类。"""

    # 子类覆盖
    name: str = "base"
    kind: str = "social"  # wecom | dingtalk | email

    def __init__(self) -> None:
        self.enabled: bool = False  # 配置就绪（关键凭证非空）
        self._last_error: str | None = None

    # ---- 配置自检（子类实现：返回是否具备运行所需凭证）----
    def _check_config(self) -> bool:
        raise NotImplementedError

    # ---- 连通性 / token 校验（子类实现）----
    async def test_connection(self) -> dict:
        raise NotImplementedError

    # ---- 发布到 UNS social 通道（隐性捕获统一入口）----
    def publish(
        self,
        text: str,
        entities: list | None = None,
        source: str | None = None,
        confidence: float = 1.0,
        extra: dict | None = None,
    ) -> Any:
        """把一条社交信号经 token 鉴权后喂入 UNS social 路。

        返回 UNS 事件 id（韧性：失败返回 None，不抛）。
        """
        try:
            from src.runtime.uns import uns, CHANNEL_SOCIAL

            payload = {"content": text, **(extra or {})}
            ev = uns.publish(
                CHANNEL_SOCIAL,
                source or f"{self.kind}://{self.name}",
                "business_event",
                payload=payload,
                entities=entities or [],
                confidence=confidence,
            )
            logger.info(f"✅ [{self.name}] 社交信号已入 UNS social：{text[:50]}")
            return ev.id
        except Exception as e:
            logger.warning(f"⚠️ [{self.name}] 发布 UNS 失败（不破管）：{e}")
            return None

    def status(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "enabled": self.enabled,
            "error": self._last_error,
        }
