"""元Agent——平台健康监控

职责：
1. Runtime运行状态实时监控
2. API响应时间追踪
3. Agent执行成功率统计
4. 健康报告生成
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    status: str  # healthy / degraded / down
    uptime_seconds: float = 0.0
    api_latency_ms: float = 0.0
    active_sessions: int = 0
    total_sessions: int = 0
    success_rate: float = 1.0
    errors_last_hour: int = 0
    last_check: str = ""


@dataclass
class MetricPoint:
    timestamp: float
    value: float
    label: str


class MetaMonitor:
    """元监控——观察整个平台运行状态"""

    def __init__(self):
        self._start_time = time.time()
        self._api_latencies: list[float] = []
        self._session_results: dict[str, str] = {}  # session_id -> success/fail
        self._errors: list[dict] = []
        self._metrics: dict[str, list[MetricPoint]] = defaultdict(list)

    def record_api_call(self, duration_ms: float):
        """记录API响应时间"""
        self._api_latencies.append(duration_ms)
        # 只保留最近1000条
        if len(self._api_latencies) > 1000:
            self._api_latencies = self._api_latencies[-1000:]

    def record_session_result(self, session_id: str, success: bool, detail: str = ""):
        """记录Agent执行结果"""
        self._session_results[session_id] = "success" if success else "fail"
        if not success:
            self._errors.append({
                "session_id": session_id,
                "time": datetime.now(timezone.utc).isoformat(),
                "detail": detail,
            })

    def get_health(self) -> HealthStatus:
        """生成当前健康状态"""
        now = time.time()
        uptime = now - self._start_time

        # 计算API平均延迟
        avg_latency = (
            sum(self._api_latencies[-100:]) / len(self._api_latencies[-100:])
            if self._api_latencies else 0.0
        )

        # 计算成功率
        total = len(self._session_results)
        successes = sum(1 for v in self._session_results.values() if v == "success")
        success_rate = successes / total if total > 0 else 1.0

        # 最近1小时错误数
        recent_errors = sum(
            1 for e in self._errors
            if now - datetime.fromisoformat(e["time"]).timestamp() < 3600
        )

        # 判定状态
        if recent_errors > 10 or success_rate < 0.8:
            status = "degraded"
        elif recent_errors > 0:
            status = "degraded"
        else:
            status = "healthy"

        return HealthStatus(
            status=status,
            uptime_seconds=round(uptime, 1),
            api_latency_ms=round(avg_latency, 1),
            active_sessions=len(self._session_results),
            total_sessions=total,
            success_rate=round(success_rate, 3),
            errors_last_hour=recent_errors,
            last_check=datetime.now(timezone.utc).isoformat(),
        )

    def record_metric(self, name: str, value: float, label: str = ""):
        """记录自定义指标"""
        self._metrics[name].append(MetricPoint(
            timestamp=time.time(),
            value=value,
            label=label,
        ))

    def get_report(self) -> dict:
        """生成健康报告"""
        health = self.get_health()
        return {
            "status": health.status,
            "uptime": f"{health.uptime_seconds:.0f}s",
            "api_latency_ms": health.api_latency_ms,
            "sessions": {
                "total": health.total_sessions,
                "active": health.active_sessions,
                "success_rate": health.success_rate,
            },
            "errors_last_hour": health.errors_last_hour,
            "last_check": health.last_check,
        }


# 单例
monitor = MetaMonitor()
