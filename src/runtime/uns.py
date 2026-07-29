"""轻量统一事件总线（Unified Namespace, UNS）

六路感知归一接入（与战略文档 §3.3 事件 schema 一致，v30 五路→六路）：
    channel : gateway | system | human | social | meeting | collab | environment | environment_internal | platform_insight
    source  : opcua://line-3 | erp://sap/mm | wecom://group-x | env://policy/miit | platform://zhiyan/suggestion
    type    : sensor_reading | business_event | tacit_judgment | decision_rationale | collab_message | env_signal | platform_insight
    payload : {...结构化字段...}
    entities: [LINE:3, DEV:hyd-105, MAT:CAP-001, SUP:A, EMP:zhang]
    confidence / ts
    credibility : official | authoritative | general —— 仅⑥ environment 路必填（F4 可信治理）
                platform —— G5 轨道二平台建议专用（透明标注，绝不伪装成官方情报，F4 红线）

职责：
- 五路信号同 schema 归一入总线，可查可回溯（query / channel_counts / recent）。
- 结构化 machine 状态（gateway/system 路，带 holon 标注或 machine 前缀键）自动路由到
  twin_feed（registry.route_event），驱动孪生体状态上行 —— 即「网关实时流进 agent」的最小落地。
- collab 源：设备作为一等参与者进入协作话题（工业龙虾借鉴），与其他路并列归一。

韧性铁律：UNS 是纯内存总线，任何路由/订阅失败静默降级，绝不阻断上游（网关、外部系统照常工作）。
无外部依赖，import 即实例化单例 `uns`，无需 lifespan 初始化。
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from src.runtime.context import get_current_tenant

# ---- 六路 channel 常量（与战略文档 §3.3 完全一致，v30 新增 environment）----
CHANNEL_GATEWAY = "gateway"
CHANNEL_SYSTEM = "system"
CHANNEL_HUMAN = "human"
CHANNEL_SOCIAL = "social"
CHANNEL_MEETING = "meeting"
CHANNEL_COLLAB = "collab"
CHANNEL_ENVIRONMENT = "environment"
CHANNEL_ENVIRONMENT_INTERNAL = "environment_internal"  # 内部研究专用（上铁实证），绝不进客户面共享池
CHANNEL_PLATFORM_INSIGHT = "platform_insight"

ALL_CHANNELS = (
    CHANNEL_GATEWAY,
    CHANNEL_SYSTEM,
    CHANNEL_HUMAN,
    CHANNEL_SOCIAL,
    CHANNEL_MEETING,
    CHANNEL_COLLAB,
    CHANNEL_ENVIRONMENT,
    CHANNEL_ENVIRONMENT_INTERNAL,
    CHANNEL_PLATFORM_INSIGHT,
)

# ---- F4 可信治理：credibility 分级（仅 environment 路必填）----
CRED_OFFICIAL = "official"          # 官方发布（部委/交易所/标准机构）→ 直接锚定
CRED_AUTHORITATIVE = "authoritative"  # 权威媒体/行业协会 → 进 _needs_review
CRED_GENERAL = "general"            # 一般来源 → 进 _needs_review
CREDIBILITY_LEVELS = (CRED_OFFICIAL, CRED_AUTHORITATIVE, CRED_GENERAL)
# G5 轨道二：智衍平台建议专用可信标签（透明标注，与 official 真实情报严格区分，F4 红线）
CRED_PLATFORM = "platform"

# 结构化 machine 状态 tag 前缀（前缀猜测模式下路由到 machine holon）
MACHINE_STATE_PREFIXES = (
    "energy_kwh__",
    "power_kw__",
    "green_ratio__",
    "oee__",
    "temp__",
    "vibration__",
    "status__",
    "pressure__",
    "flow__",
)

# 结构化状态上行（gateway/system 路）才会被路由到 twin_feed
ROUTEABLE_CHANNELS = (CHANNEL_GATEWAY, CHANNEL_SYSTEM)


@dataclass
class UNSEvent:
    """总线上的统一事件（同 schema）。route_holon 为内部路由用，不进 to_dict。"""

    id: str
    channel: str
    source: str
    type: str
    payload: dict
    entities: list
    confidence: float
    ts: float
    credibility: str | None = None  # F4 可信治理：仅 environment 路必填（official/authoritative/general）
    route_holon: str | None = None  # 内部：结构化状态上行目标 holon（如 machine/material）
    tenant_id: str = "default"  # P1① 租户隔离：发布时快照请求租户（contextvars），下游锚定按此落库

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "channel": self.channel,
            "source": self.source,
            "type": self.type,
            "payload": self.payload,
            "entities": self.entities,
            "confidence": self.confidence,
            "ts": self.ts,
            "tenant_id": self.tenant_id,
        }
        if self.credibility is not None:
            d["credibility"] = self.credibility
        return d


class UnifiedNamespace:
    """轻量统一事件总线（内存环形缓冲 + 可选订阅 + twin_feed 自动路由）。"""

    def __init__(self, maxlen: int = 5000):
        # P1⑤ 并发安全：deque(maxlen) 原子环形淘汰 + RLock 保护共享状态。
        # publish 是同步方法，会被 asyncio 协程与后台线程（连接器轮询）同时调用，
        # 因此用 threading.RLock 而非 asyncio.Lock（后者只能在 await 中使用）。
        self._events: deque[UNSEvent] = deque(maxlen=maxlen)
        self._maxlen = maxlen
        self._subscribers: dict[str, list[Callable[[UNSEvent], Any]]] = {}
        self._lock = threading.RLock()

    # ---------------- 发布 ----------------
    def publish(
        self,
        channel: str,
        source: str,
        type: str,
        payload: dict | None = None,
        entities: list | None = None,
        confidence: float = 1.0,
        route_holon: str | None = None,
        credibility: str | None = None,
        tenant_id: str | None = None,
    ) -> UNSEvent:
        # F4 可信治理：environment 路必须带合法 credibility；缺失/非法一律降为 general（保守不丢弃）
        if channel == CHANNEL_ENVIRONMENT and credibility not in CREDIBILITY_LEVELS:
            credibility = CRED_GENERAL
        ev = UNSEvent(
            id=str(uuid.uuid4()),
            channel=channel,
            source=source,
            type=type,
            payload=dict(payload or {}),
            entities=list(entities or []),
            confidence=confidence,
            ts=time.time(),
            credibility=credibility,
            route_holon=route_holon,
            # P1① 租户快照：显式传入 > 请求上下文（require_auth 已 set_current_tenant）> default
            tenant_id=tenant_id or get_current_tenant(),
        )
        # P1⑤ 并发安全：追加 + 订阅者快照在锁内完成；deque(maxlen) 自动环形淘汰
        with self._lock:
            self._events.append(ev)
            handlers = list(self._subscribers.get(ev.channel, []))
        # 结构化状态上行（gateway/system 路）→ twin_feed（锁外执行，避免 handler 反入总线死锁/长占锁）
        self._route_to_twin(ev)
        # 广播给订阅者（快照遍历，锁外执行）
        self._notify(ev, handlers)
        return ev

    # 五路便捷入口
    def publish_gateway(self, source, payload, entities=None, type="sensor_reading", confidence=1.0, route_holon="machine"):
        return self.publish(CHANNEL_GATEWAY, source, type, payload, entities, confidence, route_holon=route_holon)

    def publish_system(self, source, payload, entities=None, type="business_event", confidence=1.0, route_holon="machine"):
        return self.publish(CHANNEL_SYSTEM, source, type, payload, entities, confidence, route_holon=route_holon)

    def publish_human(self, source, payload, entities=None, type="tacit_judgment", confidence=1.0):
        return self.publish(CHANNEL_HUMAN, source, type, payload, entities, confidence)

    def publish_social(self, source, payload, entities=None, type="business_event", confidence=1.0):
        return self.publish(CHANNEL_SOCIAL, source, type, payload, entities, confidence)

    def publish_meeting(self, source, payload, entities=None, type="decision_rationale", confidence=1.0):
        return self.publish(CHANNEL_MEETING, source, type, payload, entities, confidence)

    def publish_collab(self, source, payload, entities=None, type="collab_message", confidence=1.0):
        return self.publish(CHANNEL_COLLAB, source, type, payload, entities, confidence)

    def publish_environment(self, source, payload, entities=None, type="env_signal", confidence=1.0, credibility=CRED_GENERAL):
        """第⑥路环境感知：外部世界信号（政策/行情/对标等），credibility 必填（F4 可信治理）。"""
        return self.publish(CHANNEL_ENVIRONMENT, source, type, payload, entities, confidence, credibility=credibility)

    def publish_environment_internal(self, source, payload, entities=None, type="env_signal", confidence=1.0, credibility=CRED_GENERAL):
        """内部研究专用环境通道（如上市企业公告披露 / 上铁通信实证）。

        🔴 与 CHANNEL_ENVIRONMENT 严格分离：所有客户面消费方（孪生大屏体外感知、/environment/signals、
        平台建议派生、BOM 毛利测算、agents 环境消费）只查 CHANNEL_ENVIRONMENT，天然读不到此通道。
        即「上铁实证」仅内部研究与实测、不对外宣传、非外界可见公开服务的硬性隔离。
        """
        return self.publish(CHANNEL_ENVIRONMENT_INTERNAL, source, type, payload, entities, confidence, credibility=credibility)

    def publish_platform_insight(self, source, payload, entities=None, type="platform_insight", confidence=1.0, tenant_id=None):
        """G5 轨道二：智衍平台基于真实情报生成的建议/解读（透明标注 credibility=platform）。

        与 environment 路（真实外部情报）严格分离——绝不在 platform_insight 通道伪装官方情报（F4 红线）。
        每条建议的 payload 须带 based_on 透明溯源其依据的真实情报；credibility 固定为 platform。
        """
        return self.publish(
            CHANNEL_PLATFORM_INSIGHT, source, type, payload, entities, confidence,
            credibility=CRED_PLATFORM, tenant_id=tenant_id,
        )

    # ---------------- 路由：结构化状态 → twin_feed（韧性降级）----------------
    def _route_to_twin(self, ev: UNSEvent) -> None:
        if ev.channel not in ROUTEABLE_CHANNELS:
            return
        try:
            if ev.route_holon:
                values = {k: v for k, v in ev.payload.items() if not k.startswith("_")}
                holon = ev.route_holon
            else:
                values = {
                    k: v
                    for k, v in ev.payload.items()
                    if any(k.startswith(p) for p in MACHINE_STATE_PREFIXES)
                }
                if not values:
                    return
                holon = "machine"
            # 延迟 import，避免与 data_sources 形成循环依赖
            from src.runtime.data_sources.registry import registry

            registry.route_event(holon, values, source=ev.source)
        except Exception:
            # 韧性降级：twin_feed 不可达 / 无对应孪生体 → 不阻断 UNS 与上游
            pass

    # ---------------- 订阅（可选，轻量）----------------
    def subscribe(self, channel: str, handler: Callable[[UNSEvent], Any]) -> None:
        with self._lock:
            self._subscribers.setdefault(channel, []).append(handler)

    def _notify(self, ev: UNSEvent, handlers: list[Callable[[UNSEvent], Any]] | None = None) -> None:
        # P1⑤ 并发安全：优先用 publish 传入的锁内快照；单独调用时自行取快照
        if handlers is None:
            with self._lock:
                handlers = list(self._subscribers.get(ev.channel, []))
        for h in handlers:
            try:
                h(ev)
            except Exception:
                pass

    # ---------------- 查询（可查可回溯）----------------
    def query(self, channel: str | None = None, n: int | None = None) -> list[dict]:
        with self._lock:
            snapshot = list(self._events)
        evs = snapshot if channel is None else [e for e in snapshot if e.channel == channel]
        if n is not None:
            evs = evs[-n:]
        return [e.to_dict() for e in evs]

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            snapshot = list(self._events)
        return [e.to_dict() for e in snapshot[-n:]]

    def channel_counts(self) -> dict:
        with self._lock:
            snapshot = list(self._events)
        counts: dict[str, int] = {}
        for e in snapshot:
            counts[e.channel] = counts.get(e.channel, 0) + 1
        return counts

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._subscribers.clear()


# 进程级单例：import 即存在，纯内存，无需 lifespan 初始化
uns = UnifiedNamespace()
