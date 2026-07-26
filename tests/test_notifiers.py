"""告警通知渠道测试（v29.1）。"""
import importlib

import pytest

from src.runtime import notifiers
from src.runtime.monitoring import AlertMonitor, Alert


class FakeNotifier(notifiers.Notifier):
    name = "fake"

    def __init__(self):
        self.sent = []

    def send(self, alert):
        self.sent.append(alert)
        return True


def _patch_registry(monkeypatch, fake):
    reg = dict(notifiers._REGISTRY)
    reg["fake"] = lambda: fake
    monkeypatch.setattr(notifiers, "_REGISTRY", reg)


def test_log_notifier_always_ok():
    a = Alert("k", "kind", "warning", "msg")
    assert notifiers.LogNotifier().send(a) is True


def test_email_no_config_returns_false(monkeypatch):
    for k in ("ZHIYAN_ALERT_EMAIL_HOST", "ZHIYAN_ALERT_EMAIL_USER",
              "ZHIYAN_ALERT_EMAIL_PASS", "ZHIYAN_ALERT_EMAIL_TO"):
        monkeypatch.delenv(k, raising=False)
    a = Alert("k", "kind", "warning", "msg")
    assert notifiers.EmailNotifier().send(a) is False


def test_wecom_no_webhook_returns_false(monkeypatch):
    monkeypatch.delenv("ZHIYAN_ALERT_WECOM_WEBHOOK", raising=False)
    a = Alert("k", "kind", "warning", "msg")
    assert notifiers.WeComNotifier().send(a) is False


def test_dispatch_custom_notifier(monkeypatch):
    fake = FakeNotifier()
    _patch_registry(monkeypatch, fake)
    monkeypatch.setenv("ZHIYAN_ALERT_NOTIFIERS", "fake")
    a = Alert("k", "kind", "critical", "boom")
    n = notifiers.dispatch_notifications(a)
    assert n == 1
    assert fake.sent == [a]


def test_fire_dispatches_to_channel(monkeypatch):
    fake = FakeNotifier()
    _patch_registry(monkeypatch, fake)
    monkeypatch.setenv("ZHIYAN_ALERT_NOTIFIERS", "fake")
    m = AlertMonitor()
    m.clear()
    a = Alert("login_anomaly:admin", "login_anomaly", "critical", "x")
    fired = m._fire(a)
    assert fired is True
    assert fake.sent and fake.sent[0].key == "login_anomaly:admin"
    assert a.notified == 1


def test_status_reports_notifiers(monkeypatch):
    fake = FakeNotifier()
    _patch_registry(monkeypatch, fake)
    monkeypatch.setenv("ZHIYAN_ALERT_NOTIFIERS", "fake,log")
    assert "fake" in AlertMonitor().status()["notifiers"]
