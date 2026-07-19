"""元Agent——告警引擎

基于监控数据，自动触发告警通知。
MVP阶段：控制台告警面板展示
V1阶段：接入企业微信/钉钉/邮件
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    level: str  # info / warning / critical
    title: str
    message: str
    source: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = False


class AlertEngine:
    """告警引擎"""

    def __init__(self):
        self._alerts: list[Alert] = []
        self._rules = {
            "api_latency_high": {"threshold": 5000, "level": "warning"},  # API延迟>5秒警告
            "api_latency_critical": {"threshold": 10000, "level": "critical"},
            "session_failure_rate": {"threshold": 0.2, "level": "critical"},  # 失败率>20%
            "errors_burst": {"threshold": 10, "window_minutes": 60, "level": "critical"},
        }

    def evaluate(self, monitor_data: dict) -> list[Alert]:
        """根据监控数据评估并触发告警"""
        triggered = []

        # 检查API延迟
        latency = monitor_data.get("api_latency_ms", 0)
        if latency > self._rules["api_latency_critical"]["threshold"]:
            triggered.append(Alert(
                level="critical",
                title="API延迟过高",
                message=f"平均延迟 {latency:.0f}ms，超过临界阈值 {self._rules['api_latency_critical']['threshold']}ms",
                source="meta-monitor",
            ))
        elif latency > self._rules["api_latency_high"]["threshold"]:
            triggered.append(Alert(
                level="warning",
                title="API延迟偏高",
                message=f"平均延迟 {latency:.0f}ms，超过警告阈值",
                source="meta-monitor",
            ))

        # 检查Session失败率
        sessions = monitor_data.get("sessions", {})
        success_rate = sessions.get("success_rate", 1.0)
        if success_rate < (1 - self._rules["session_failure_rate"]["threshold"]):
            triggered.append(Alert(
                level="critical",
                title="Agent执行失败率过高",
                message=f"成功率 {success_rate:.1%}，低于安全阈值",
                source="meta-monitor",
            ))

        # 记录告警
        for alert in triggered:
            self._alerts.append(alert)
            logger.warning(f"[ALERT] {alert.level.upper()} | {alert.title}")

        return triggered

    def acknowledge(self, alert_index: int) -> bool:
        """确认告警"""
        if 0 <= alert_index < len(self._alerts):
            self._alerts[alert_index].acknowledged = True
            return True
        return False

    def get_active_alerts(self) -> list[Alert]:
        return [a for a in self._alerts if not a.acknowledged]


# 单例
alert_engine = AlertEngine()
