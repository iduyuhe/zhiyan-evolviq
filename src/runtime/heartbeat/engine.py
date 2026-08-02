"""Agent 心跳自触发引擎（Heartbeat Engine，2026-08-02）

OpenClaw（小龙虾）HEARTBEAT 模式借鉴——「从被动应答到主动巡检」：
- 定时触发巡检 Agent（复用 analyze(mode="heartbeat")，不新建 Agent）
- 静默门控：无风险 → 静默（不产生告警，不打扰）
- 有风险 → 复用 AlertMonitor._fire 发布告警（cooldown 去重 + UNS system 路 + 通知渠道）

🔴 不扩边缘：0 新 Agent、0 新端点、0 新界面——巡检复用现有 Agent 的 analyze，
告警复用现有 /monitoring/alerts + AlertPanel 展示。
🔴 默认关闭：ZHIYAN_HEARTBEAT_ENABLED=1 才启动（避免演示环境噪音，先有后优）。
🔴 韧性：单次巡检失败静默降级（日志），绝不阻塞平台；心跳不写租户记忆（mode=heartbeat 视同 research_case 纪律）。
🔴 事实锚点：风险判定只认 Agent 返回的结构化字段，不编造风险。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _risk_judge_supply_chain(result: dict) -> str | None:
    """缺料风险：risk_items_before/total > 0 → 返回风险描述，否则 None（静默）。"""
    n = int(result.get("risk_items_before") or result.get("risk_items_total") or 0)
    if n > 0:
        return f"缺料风险项 {n} 项（high/critical）"
    return None


def _risk_judge_bid_intel(result: dict) -> str | None:
    """商机：捕获到新商机信号 → 值得推送。"""
    opps = result.get("opportunities") or []
    if opps:
        titles = "、".join(o.get("title", "")[:24] for o in opps[:3])
        return f"捕获 {len(opps)} 个商机信号（{titles}）"
    return None


def _risk_judge_energy_carbon(result: dict) -> str | None:
    """能耗风险：碳强度超标（intensity_gap > 0）或绿电过低。"""
    gap = result.get("intensity_gap")
    if isinstance(gap, (int, float)) and gap > 0:
        return f"碳强度超目标 {gap:g} tCO2/万元"
    green = result.get("green_ratio")
    if isinstance(green, (int, float)) and green < 15:
        return f"绿电比例过低 {green:g}%（<15%）"
    return None


class HeartbeatEngine:
    """心跳引擎：按 per-agent 频率后台触发巡检。"""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._enabled = False
        self._last_run: dict[str, float] = {}
        self._runs = 0
        self._alerts = 0

    # 巡检注册表：agent → (goal, 频率秒, 风险判定, 严重度, 巡检标签)
    _PATROLS: list[tuple[str, str, int, Callable[[dict], str | None], str, str]] = [
        ("supply_chain", "心跳巡检：检查物料齐套与缺料风险", 1800, _risk_judge_supply_chain, "critical", "缺料巡检"),
        ("bid_intel", "心跳巡检：扫描商机情报信号", 14400, _risk_judge_bid_intel, "warning", "商机扫描"),
        ("energy_carbon", "心跳巡检：检查能耗与碳强度异常", 3600, _risk_judge_energy_carbon, "warning", "能耗巡检"),
    ]

    @property
    def enabled(self) -> bool:
        return self._enabled

    def stats(self) -> dict:
        return {
            "enabled": self._enabled,
            "patrols": len(self._PATROLS),
            "runs": self._runs,
            "alerts": self._alerts,
            "last_run": {k: v for k, v in self._last_run.items()},
        }

    def configure(self) -> bool:
        """读 settings 决定是否启用（幂等，可多次调用）。"""
        try:
            from src.common.config import settings

            self._enabled = bool(settings.heartbeat_enabled)
        except Exception:
            self._enabled = False
        if self._enabled:
            # 频率从 settings 读取（每个巡检的 interval 可被 env 覆盖）
            try:
                from src.common.config import settings

                self._PATROLS[0] = (self._PATROLS[0][0], self._PATROLS[0][1], int(settings.heartbeat_interval_supply_chain), *self._PATROLS[0][3:])
                self._PATROLS[1] = (self._PATROLS[1][0], self._PATROLS[1][1], int(settings.heartbeat_interval_bid_intel), *self._PATROLS[1][3:])
                self._PATROLS[2] = (self._PATROLS[2][0], self._PATROLS[2][1], int(settings.heartbeat_interval_energy_carbon), *self._PATROLS[2][3:])
            except Exception:
                pass
        logger.info(f"💓 心跳引擎：{'已启用' if self._enabled else '未启用（ZHIYAN_HEARTBEAT_ENABLED=1 开启）'}")
        return self._enabled

    async def start(self) -> None:
        """启动所有巡检后台任务（幂等；未启用则 no-op）。"""
        if not self._enabled or self._tasks:
            return
        for agent, goal, interval, judge, severity, label in self._PATROLS:
            task = asyncio.create_task(
                self._patrol_loop(agent, goal, interval, judge, severity, label),
                name=f"heartbeat:{agent}",
            )
            self._tasks.append(task)
            logger.info(f"💓 心跳巡检已启动：{label}（{agent}，每 {interval}s）")

    def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    async def patrol_once(self, agent: str, goal: str, judge: Callable[[dict], str | None],
                          severity: str, label: str) -> dict:
        """执行单次巡检：analyze(mode=heartbeat) → 风险判定 → 告警发布。返回执行摘要。"""
        from src.runtime.agent.router import get_agent

        agent_obj = get_agent(agent)
        # 🔴 heartbeat 视同 research_case 纪律：不写租户记忆、不执行商务/生产动作
        # （各 Agent 签名不同，只传统一入参 goal/mode；tenant 取各自默认）
        result = await agent_obj.analyze(goal, mode="heartbeat")
        self._runs += 1
        self._last_run[agent] = time.time()

        risk_text = None
        try:
            risk_text = judge(result)
        except Exception as e:
            logger.warning(f"⚠️ [heartbeat:{agent}] 风险判定异常（静默）：{e}")

        if not risk_text:
            logger.info(f"💓 [heartbeat:{agent}] {label}：无风险（静默）")
            return {"agent": agent, "fired": False, "detail": "无风险，静默"}

        # 🔴 复用 AlertMonitor：cooldown 去重 + UNS system 路 + 通知渠道 + /monitoring/alerts
        try:
            from src.runtime.monitoring import alert_monitor
            from src.runtime.monitoring import Alert

            fired = alert_monitor._fire(Alert(
                key=f"heartbeat:{agent}",
                kind="heartbeat_risk",
                severity=severity,
                message=f"[心跳·{label}] {risk_text}",
                detail={
                    "agent": agent,
                    "label": label,
                    "risk": risk_text,
                    "summary": (result.get("summary") or "")[:200],
                },
            ))
            if fired:
                self._alerts += 1
            return {"agent": agent, "fired": fired, "detail": risk_text}
        except Exception as e:
            logger.warning(f"⚠️ [heartbeat:{agent}] 告警发布失败（不破管）：{e}")
            return {"agent": agent, "fired": False, "detail": f"发布异常：{e}"}

    async def _patrol_loop(self, agent: str, goal: str, interval: int,
                           judge: Callable[[dict], str | None], severity: str, label: str) -> None:
        """巡检循环：首轮立即执行一次，随后按间隔。单次失败静默继续。"""
        while True:
            try:
                await self.patrol_once(agent, goal, judge, severity, label)
            except Exception as e:
                logger.warning(f"⚠️ [heartbeat:{agent}] 巡检失败（静默继续）：{e}")
            await asyncio.sleep(max(interval, 60))


# 进程级单例
heartbeat_engine = HeartbeatEngine()
