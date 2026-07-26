"""邮件渠道接入器（v29.9）—— IMAP 轮询拉取

- 用标准库 imaplib（始终可用），登录 → 取未读邮件 → 解析业务事件 → 入 UNS social 路。
- 敏感内容（薪资/离职/密码/合同金额等）走审批门：payload._needs_review=True + 降置信度，
  由隐性捕获管线标记待人工批准再锚定图谱。
- 韧性：连接/登录失败静默降级（enabled 视配置；test_connection 实测连通性）。
"""

from __future__ import annotations

import email
import imaplib
import logging
import socket
import time
from email.header import decode_header
from typing import Any

from src.common.config import settings
from src.runtime.connectors.base import SocialConnectorBase

logger = logging.getLogger(__name__)

# 敏感关键词（命中则走审批门）
SENSITIVE_KEYWORDS = (
    "薪资", "工资", "离职", "密码", "合同金额", "薪酬", "补偿", "仲裁", "诉讼",
    "salary", "resign", "password", "compensation", "lawsuit",
)


class EmailConnector(SocialConnectorBase):
    name = "email"
    kind = "email"

    def __init__(self) -> None:
        super().__init__()
        self.host = settings.email_imap_host
        self.user = settings.email_imap_user
        self.password = settings.email_imap_password
        self.mailbox = settings.email_imap_mailbox or "INBOX"
        self.poll_interval = settings.email_poll_interval or 300
        self.enabled = bool(self.host and self.user and self.password)

    def _connect(self) -> Any:
        """建立 IMAP 连接（带超时，避免阻塞）。失败时抛异常由调用方降级。

        统一走 SSL（企业邮箱绝大多数支持）；如需非 SSL 端口可在此扩展分支。
        """
        client = imaplib.IMAP4_SSL(self.host, timeout=10)
        client.login(self.user, self.password)
        return client

    async def test_connection(self) -> dict:
        t0 = time.monotonic()
        if not self.enabled:
            return {
                "name": self.name, "kind": self.kind, "ok": False,
                "mode": "not_configured",
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
                "detail": "未配置 ZHIYAN_EMAIL_IMAP_*",
            }
        try:
            c = self._connect()
            c.select(self.mailbox)
            c.logout()
            return {
                "name": self.name, "kind": self.kind, "ok": True,
                "mode": "connected",
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
                "detail": f"IMAP 登录成功：{self.host}",
            }
        except (socket.timeout, OSError, imaplib.IMAP4.error) as e:
            self._last_error = str(e)
            return {
                "name": self.name, "kind": self.kind, "ok": False,
                "mode": "error",
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
                "detail": f"IMAP 连接失败：{e}",
            }

    def _decode_str(self, s: str) -> str:
        try:
            parts = decode_header(s)
            return "".join(
                (bytes(p, "utf-8") if isinstance(p, str) else p).decode("utf-8", "ignore")
                if isinstance(p, (bytes, str)) else ""
                for p, enc in parts
            )
        except Exception:
            return s

    def _is_sensitive(self, text: str) -> bool:
        low = text.lower()
        return any(k.lower() in low for k in SENSITIVE_KEYWORDS)

    async def pull(self, limit: int = 20) -> dict:
        """拉取未读邮件 → 发布到 UNS social。返回 {pulled, published, sensitive}。"""
        if not self.enabled:
            return {"pulled": 0, "published": 0, "sensitive": 0, "detail": "未配置"}
        try:
            c = self._connect()
            c.select(self.mailbox)
            status, data = c.search(None, "UNSEEN")
            ids = data[0].split() if data and data[0] else []
            published = 0
            sensitive = 0
            for mid in ids[:limit]:
                try:
                    _, msg_data = c.fetch(mid, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    subject = self._decode_str(msg.get("Subject", ""))
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", "ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", "ignore")
                    text = f"{subject}\n{body}".strip()
                    is_sens = self._is_sensitive(text)
                    evt_id = self.publish(
                        text=text[:500],
                        entities=[f"email:{msg.get('From', 'unknown')}"],
                        source=f"email://{self.host}",
                        confidence=0.6 if is_sens else 1.0,
                        extra={"_needs_review": is_sens, "subject": subject[:120]},
                    )
                    if evt_id:
                        published += 1
                        if is_sens:
                            sensitive += 1
                    # 标记为已读（避免重复拉取）
                    c.store(mid, "+FLAGS", "\\Seen")
                except Exception as e:
                    logger.warning(f"⚠️ 邮件单条处理失败：{e}")
            c.logout()
            return {"pulled": len(ids[:limit]), "published": published, "sensitive": sensitive}
        except Exception as e:
            self._last_error = str(e)
            logger.warning(f"⚠️ 邮件拉取失败（不破管）：{e}")
            return {"pulled": 0, "published": 0, "sensitive": 0, "detail": str(e)}
