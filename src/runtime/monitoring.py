"""监控告警（v28.3）——三类生产级异常的检测与告警

覆盖三类告警（对应生产运维的三大盲区）：
    1. writeback_backlog   回写 pending 积压超阈值（ERP/MES 连接器长期不可达）
    2. gateway_stale       网关断流：孪生体 twin_state 超期未更新（实时流中断）
    3. login_anomaly       登录失败异常：滑动窗口内失败次数超阈值（暴力破解嫌疑）

告警出口：
    - UNS system 路（source=monitor://alerts, type=alert）——进统一事件总线可查可回溯；
    - 本地环形缓冲 alerts()——供 /monitoring/alerts API 查询。

阈值 env 可调（默认值生产可用）：
    ZHIYAN_ALERT_WB_PENDING     回写积压阈值（条，默认 10）
    ZHIYAN_ALERT_TWIN_STALE_S   孪生体断流阈值（秒，默认 600）
    ZHIYAN_ALERT_LOGIN_FAILS    登录失败次数阈值（默认 5）
    ZHIYAN_ALERT_LOGIN_WINDOW_S 登录失败统计窗口（秒，默认 300）

韧性铁律：检测/发布告警任何异常静默降级，绝不阻断业务主流程。
去重：同一 alert key 在 cooldown（默认 300s）内不重复发布。
进程级单例 `alert_monitor`。
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, "") or default)
    except ValueError:
        return default


@dataclass
class Alert:
    key: str            # 去重键，如 writeback_backlog / gateway_stale:energy_twin / login_anomaly:admin
    kind: str           # writeback_backlog | gateway_stale | login_anomaly
    severity: str       # warning | critical
    message: str
    detail: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    notified: int = 0  # 成功送达的通知渠道数

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "detail": self.detail,
            "ts": self.ts,
            "notified": self.notified,
        }


class AlertMonitor:
    """三类生产异常的检测器 + 告警缓冲（进程级单例语义）。"""

    def __init__(self):
        self._alerts: list[Alert] = []
        self._max_kept = 200
        self._last_fired: dict[str, float] = {}   # 去重：key -> 上次发布时间
        self.cooldown_s = 300
        # 登录失败滑动窗口：username -> [失败时间戳...]
        self._login_fails: dict[str, list[float]] = {}

    # ---------------- 阈值（运行时读 env，实时生效） ----------------

    @property
    def wb_pending_threshold(self) -> int:
        return _env_int("ZHIYAN_ALERT_WB_PENDING", 10)

    @property
    def twin_stale_threshold_s(self) -> int:
        return _env_int("ZHIYAN_ALERT_TWIN_STALE_S", 600)

    @property
    def login_fail_threshold(self) -> int:
        return _env_int("ZHIYAN_ALERT_LOGIN_FAILS", 5)

    @property
    def login_window_s(self) -> int:
        return _env_int("ZHIYAN_ALERT_LOGIN_WINDOW_S", 300)

    # ---------------- 告警发布（UNS + 本地缓冲，去重） ----------------

    def _fire(self, alert: Alert) -> bool:
        """发布告警。cooldown 内同 key 去重；返回是否实际发布。"""
        now = time.time()
        last = self._last_fired.get(alert.key, 0)
        if now - last < self.cooldown_s:
            return False
        self._last_fired[alert.key] = now
        self._alerts.append(alert)
        if len(self._alerts) > self._max_kept:
            self._alerts = self._alerts[-self._max_kept:]
        # UNS system 路（韧性：失败静默）
        try:
            from src.runtime.uns import uns
            uns.publish(
                channel="system",
                source="monitor://alerts",
                type="alert",
                payload=alert.to_dict(),
                route_holon=None,
            )
        except Exception:
            pass
        # 通知渠道（邮件/企业微信/日志）——单渠道失败静默
        try:
            from src.runtime.notifiers import dispatch_notifications
            alert.notified = dispatch_notifications(alert)
        except Exception:
            pass
        logger.warning(f"🚨 [{alert.severity}] {alert.kind}: {alert.message}")
        return True

    # ---------------- ① 回写积压 ----------------

    def check_writeback_backlog(self) -> Alert | None:
        try:
            from src.runtime.data_sources.writeback import writeback_bridge
            n = len(writeback_bridge.pending())
        except Exception:
            return None
        if n < self.wb_pending_threshold:
            return None
        alert = Alert(
            key="writeback_backlog",
            kind="writeback_backlog",
            severity="critical" if n >= self.wb_pending_threshold * 2 else "warning",
            message=f"回写 pending 积压 {n} 条（阈值 {self.wb_pending_threshold}），ERP/MES 连接器疑似长期不可达",
            detail={"pending": n, "threshold": self.wb_pending_threshold},
        )
        return alert if self._fire(alert) else None

    # ---------------- ② 网关断流（孪生体超期） ----------------

    def check_gateway_stale(self, tenant_id: str = "default") -> list[Alert]:
        fired: list[Alert] = []
        try:
            from src.runtime.data_sources.registry import registry
            sources = registry.get_for_tenant(tenant_id).values()
        except Exception:
            return fired
        now = time.time()
        for src in sources:
            try:
                state = src.get_twin_state()
            except Exception:
                continue
            updated = state.get("updated_at")
            if updated is None:
                continue  # 从未有流入的孪生体不算断流（可能未接网关）
            age = now - updated
            if age < self.twin_stale_threshold_s:
                continue
            alert = Alert(
                key=f"gateway_stale:{src.name}",
                kind="gateway_stale",
                severity="critical",
                message=f"孪生体 {src.name} 已 {int(age)}s 无实时流入（阈值 {self.twin_stale_threshold_s}s），网关疑似断流",
                detail={"source": src.name, "tenant_id": tenant_id,
                        "stale_seconds": int(age), "threshold_s": self.twin_stale_threshold_s},
            )
            if self._fire(alert):
                fired.append(alert)
        return fired

    # ---------------- ④ 网关 simulated 降级（P1②：不再静默喂假数据） ----------------

    def report_gateway_degraded(self, gateway: str, tenant_id: str = "default",
                                phase: str = "startup") -> Alert | None:
        """网关 connect 失败回退 simulated 时显性告警（网关层调用）。

        phase: startup（首连回退）| persistent（升级重试用尽仍 simulated）。
        运营者必须知道大屏/agent 消费的是仿真数据而非真实产线数据。
        """
        alert = Alert(
            key=f"gateway_degraded:{tenant_id}:{gateway}",
            kind="gateway_degraded",
            severity="critical" if phase == "persistent" else "warning",
            message=(
                f"网关 {gateway} 处于 simulated 仿真模式（{'升级重试已用尽' if phase == 'persistent' else '真实连接失败已回退'}），"
                f"当前上行数据为仿真数据，非真实产线数据"
            ),
            detail={"gateway": gateway, "tenant_id": tenant_id,
                    "mode": "simulated", "phase": phase},
        )
        return alert if self._fire(alert) else None

    def report_gateway_recovered(self, gateway: str, mode: str,
                                 tenant_id: str = "default") -> Alert | None:
        """网关由 simulated 升级为真实连接时发恢复通知（info 级）。"""
        alert = Alert(
            key=f"gateway_recovered:{tenant_id}:{gateway}",
            kind="gateway_recovered",
            severity="info",
            message=f"网关 {gateway} 已从 simulated 升级为真实连接（{mode}），上行数据恢复为真实产线数据",
            detail={"gateway": gateway, "tenant_id": tenant_id, "mode": mode},
        )
        return alert if self._fire(alert) else None

    # ---------------- ③ 登录失败异常 ----------------

    def record_login_failure(self, username: str, ip: str = "") -> Alert | None:
        """登录失败上报（authn 层调用）。窗口内超阈值 → 告警。"""
        now = time.time()
        window = self.login_window_s
        fails = [t for t in self._login_fails.get(username, []) if now - t < window]
        fails.append(now)
        self._login_fails[username] = fails
        if len(fails) < self.login_fail_threshold:
            return None
        alert = Alert(
            key=f"login_anomaly:{username}",
            kind="login_anomaly",
            severity="critical",
            message=f"账号 {username} 在 {window}s 内登录失败 {len(fails)} 次（阈值 {self.login_fail_threshold}），疑似暴力破解",
            detail={"username": username, "ip": ip,
                    "failures": len(fails), "window_s": window,
                    "threshold": self.login_fail_threshold},
        )
        return alert if self._fire(alert) else None

    def record_login_success(self, username: str) -> None:
        """登录成功清空该账号失败窗口。"""
        self._login_fails.pop(username, None)

    # ---------------- 汇总检测 / 查询 ----------------

    def run_checks(self, tenant_id: str = "default") -> list[dict]:
        """执行一轮全量检测（回写积压 + 网关断流），返回本轮新发布的告警。"""
        fired: list[Alert] = []
        a = self.check_writeback_backlog()
        if a:
            fired.append(a)
        fired.extend(self.check_gateway_stale(tenant_id))
        return [x.to_dict() for x in fired]

    def alerts(self, kind: str | None = None, n: int = 50) -> list[dict]:
        evs = self._alerts if kind is None else [a for a in self._alerts if a.kind == kind]
        return [a.to_dict() for a in evs[-n:]]

    def status(self) -> dict:
        return {
            "alerts_total": len(self._alerts),
            "thresholds": {
                "wb_pending": self.wb_pending_threshold,
                "twin_stale_s": self.twin_stale_threshold_s,
                "login_fails": self.login_fail_threshold,
                "login_window_s": self.login_window_s,
            },
            "login_watch": {u: len(t) for u, t in self._login_fails.items() if t},
            "cooldown_s": self.cooldown_s,
            "notifiers": [n.name for n in self._notifiers()],
        }

    @staticmethod
    def _notifiers():
        try:
            from src.runtime.notifiers import get_notifiers
            return get_notifiers()
        except Exception:
            return []

    def clear(self) -> None:
        """清空（测试用）。"""
        self._alerts.clear()
        self._last_fired.clear()
        self._login_fails.clear()


async def alert_check_loop(interval: int = 60) -> None:
    """后台周期检测循环（lifespan 启动）。韧性：单轮异常吞掉继续。"""
    import asyncio
    while True:
        try:
            alert_monitor.run_checks()
        except Exception:
            pass
        await asyncio.sleep(interval)


# 进程级单例
alert_monitor = AlertMonitor()
