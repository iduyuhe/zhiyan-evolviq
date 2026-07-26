"""告警通知渠道（v29.1）——把监控告警推到人 / 外部系统。

可插拔 Notifier：
    - log         默认始终启用，仅记日志（不依赖外部服务）
    - email       通过 SMTP 发送邮件（需 ZHIYAN_ALERT_EMAIL_* 配置）
    - wechat_work  企业微信群机器人 webhook（需 ZHIYAN_ALERT_WECOM_WEBHOOK）

env 配置：
    ZHIYAN_ALERT_NOTIFIERS        启用渠道（逗号分隔，默认 "log"）
    ZHIYAN_ALERT_EMAIL_HOST/PORT/USER/PASS/TO
    ZHIYAN_ALERT_WECOM_WEBHOOK     企业微信机器人 webhook URL

韧性铁律：单渠道失败静默降级，绝不阻断告警发布主流程（_fire 已保证）。
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import urllib.request
from dataclasses import dataclass
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _env_list(key: str, default: list[str]) -> list[str]:
    v = os.environ.get(key, "")
    return [x.strip() for x in v.split(",") if x.strip()] or default


class Notifier:
    name = "base"

    def send(self, alert: "Alert") -> bool:  # noqa: ANN001 - 避免循环 import
        raise NotImplementedError


class LogNotifier(Notifier):
    name = "log"

    def send(self, alert: "Alert") -> bool:
        logger.info(f"📣 [notify/log] {alert.severity} {alert.kind}: {alert.message}")
        return True


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self):
        self.host = os.environ.get("ZHIYAN_ALERT_EMAIL_HOST", "")
        self.port = int(os.environ.get("ZHIYAN_ALERT_EMAIL_PORT", "465"))
        self.user = os.environ.get("ZHIYAN_ALERT_EMAIL_USER", "")
        self.passwd = os.environ.get("ZHIYAN_ALERT_EMAIL_PASS", "")
        self.to = _env_list("ZHIYAN_ALERT_EMAIL_TO", [])

    def send(self, alert: "Alert") -> bool:
        if not (self.host and self.user and self.passwd and self.to):
            return False
        try:
            body = f"{alert.message}\n\n细节: {json.dumps(alert.detail, ensure_ascii=False)}"
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = f"[智衍告警] {alert.severity} {alert.kind}"
            msg["From"] = self.user
            msg["To"] = ", ".join(self.to)
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.host, self.port, context=ctx) as s:
                s.login(self.user, self.passwd)
                s.send_message(msg)
            return True
        except Exception as e:  # 单渠道失败静默
            logger.warning(f"email notifier failed: {e}")
            return False


class WeComNotifier(Notifier):
    name = "wechat_work"

    def __init__(self):
        self.webhook = os.environ.get("ZHIYAN_ALERT_WECOM_WEBHOOK", "")

    def send(self, alert: "Alert") -> bool:
        if not self.webhook:
            return False
        try:
            content = (
                f"### 🚨 智衍告警 [{alert.severity}]\n"
                f">**类型**: {alert.kind}\n"
                f">**详情**: {alert.message}"
            )
            payload = {"msgtype": "markdown", "markdown": {"content": content}}
            req = urllib.request.Request(
                self.webhook,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception as e:  # 单渠道失败静默
            logger.warning(f"wecom notifier failed: {e}")
            return False


_REGISTRY: dict[str, type[Notifier]] = {
    "log": LogNotifier,
    "email": EmailNotifier,
    "wechat_work": WeComNotifier,
}


def get_notifiers() -> list[Notifier]:
    names = _env_list("ZHIYAN_ALERT_NOTIFIERS", ["log"])
    out: list[Notifier] = []
    for n in names:
        cls = _REGISTRY.get(n)
        if cls:
            try:
                out.append(cls())
            except Exception:
                pass
    if not out:
        out.append(LogNotifier())
    return out


def dispatch_notifications(alert: "Alert") -> int:
    """把告警推到所有启用渠道。返回成功数（用于状态展示）。"""
    sent = 0
    for n in get_notifiers():
        try:
            if n.send(alert):
                sent += 1
        except Exception:
            pass
    return sent
