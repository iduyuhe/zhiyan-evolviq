"""钉钉回调接入器（v29.9）

钉钉「智能群助手 / 连接平台」回调采用加签校验：
    sign = base64( HmacSHA256( f"{timestamp}\\n{secret}", secret ) )
服务端用配置的机器人 secret 重算 sign 与请求携带的 sign 比对。

- secret 缺失 → enabled=False（回调直接 403）。
- POST 体为 JSON：{ text:{content}, msgtype, ... } 或连接平台事件体（取 content）。
- 韧性：cryptography/hmac 均标准库可用；校验失败返回 None（调用方判 403）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from src.common.config import settings
from src.runtime.connectors.base import SocialConnectorBase

logger = logging.getLogger(__name__)


def verify_dingtalk_sign(secret: str, timestamp: str, sign: str) -> bool:
    """钉钉加签校验。单测核心断言对象。"""
    if not secret or not sign:
        return False
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    expected = base64.b64encode(hmac_code).decode("utf-8")
    return hmac.compare_digest(expected, sign)


class DingTalkConnector(SocialConnectorBase):
    name = "dingtalk"
    kind = "dingtalk"

    def __init__(self) -> None:
        super().__init__()
        self.secret = settings.dingtalk_secret
        self.app_key = settings.dingtalk_app_key
        self.app_secret = settings.dingtalk_app_secret
        self.enabled = bool(self.secret)

    def verify_and_parse(self, timestamp: str, sign: str, body: bytes) -> dict | None:
        """校验加签 + 解析消息体 → {content, sender, msg_type}。失败返回 None。"""
        if not verify_dingtalk_sign(self.secret, timestamp, sign):
            self._last_error = "sign mismatch"
            return None
        try:
            d = json.loads(body.decode("utf-8"))
        except Exception:
            return None
        # 群机器人 text 体：{"text":{"content": "..."}, "msgtype":"text"}
        content = ""
        if isinstance(d.get("text"), dict):
            content = d["text"].get("content", "")
        elif "content" in d:
            content = d.get("content", "")
        # 连接平台事件体可能包裹在 {"body": {...}}
        if not content and isinstance(d.get("body"), dict):
            content = d["body"].get("content", "") or str(d["body"])
        return {
            "content": content,
            "sender": d.get("senderId") or d.get("senderNick") or "unknown",
            "msg_type": d.get("msgtype") or d.get("type") or "text",
        }

    async def test_connection(self) -> dict:
        t0 = time.monotonic()
        ok = bool(self.secret)
        return {
            "name": self.name,
            "kind": self.kind,
            "ok": ok,
            "mode": "configured" if ok else "not_configured",
            "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            "detail": "机器人 secret 已配置，可接收回调" if ok else "未配置 ZHIYAN_DINGTALK_SECRET",
        }


if __name__ == "__main__":
    secret = "SECxxxx"
    ts = "1600000000"
    s = base64.b64encode(
        hmac.new(secret.encode(), f"{ts}\n{secret}".encode(), hashlib.sha256).digest()
    ).decode()
    assert verify_dingtalk_sign(secret, ts, s) is True
    assert verify_dingtalk_sign(secret, ts, "wrong") is False
    print("✅ dingtalk sign verify OK")
