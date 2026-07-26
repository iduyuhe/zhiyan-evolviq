"""网关管理器——统一持有并观测全部工业协议网关

实例化 Modbus / MQTT / OPC-UA / IPC-CFX 四类网关，提供：
- initialize()：逐个 best-effort connect，任一失败仅记日志，绝不阻断启动（韧性策略）
- health()：聚合各网关健康 + 总览（总数/就绪数/模式分布）
- get(name) / read(name, address)：按名访问

事实锚点：仅聚合真实网关状态，不改写任何业务数据。
"""

import logging

from src.common.config import settings
from src.gateways.base import DataPoint
from src.gateways.ipc_cfx.gateway import IpcCfxGateway
from src.gateways.modbus.gateway import ModbusGateway
from src.gateways.mqtt.gateway import MQTTGateway
from src.gateways.opcua.gateway import OpcUaGateway
from src.runtime.uns import uns, CHANNEL_GATEWAY

logger = logging.getLogger(__name__)


class GatewayManager:
    """统一网关管理器（单例语义，由 main lifespan 持有）

    多租户：支持按租户覆写工业协议网关连接参数。
    - 未配置 gateway_config 的租户 → 共享平台网关（默认单例 `manager`）。
    - 已配置的租户 → 惰性构建独立的 GatewayManager 实例（隔离数据源），由 get_for_tenant 返回。
    """

    def __init__(self, overrides: dict | None = None):
        cfg = {
            "modbus_host": settings.modbus_host,
            "modbus_port": settings.modbus_port,
            "mqtt_broker": settings.mqtt_broker,
            "mqtt_port": settings.mqtt_port,
            "opcua_endpoint": settings.opcua_endpoint,
            "ipc_cfx_broker": settings.ipc_cfx_broker,
        }
        if overrides:
            cfg.update({k: v for k, v in overrides.items() if k in cfg})
        self._cfg = cfg
        self._tenant_id = overrides.get("_tenant_id") if overrides else None
        self._gateways = {
            "modbus": ModbusGateway(host=cfg["modbus_host"], port=cfg["modbus_port"]),
            "mqtt": MQTTGateway(broker=cfg["mqtt_broker"], port=cfg["mqtt_port"]),
            "opcua": OpcUaGateway(endpoint=cfg["opcua_endpoint"]),
            "ipc_cfx": IpcCfxGateway(broker=cfg["ipc_cfx_broker"]),
        }
        self._initialized = False
        self._tenant_managers: dict[str, "GatewayManager"] = {}

    async def initialize(self) -> dict:
        """逐个 best-effort 连接；失败仅告警，不阻断启动。

        连接后启动「机会性升级」后台循环：若数据源服务（modbus-sim / mosquitto /
        opcua-server / rabbitmq）启动较晚，网关首次 connect 可能回退 simulated；
        后台每数秒重试一次真实连接，直到切 live 或达到最大重试次数。
        这保证 depends_on 仅 service_started（非 healthy）时，网关最终仍自动升级。
        """
        summary = {}
        for name, gw in self._gateways.items():
            try:
                ok = await gw.connect()
                summary[name] = "ready" if ok else "failed"
            except Exception as e:
                logger.warning(f"⚠️ 网关 {name} 初始化失败（不破管）：{e}")
                summary[name] = "error"
            # 启动机会性升级循环（仅 simulated 时重试真实连接）
            try:
                asyncio.create_task(self._upgrade_loop(name, gw))
            except Exception:
                pass
        self._initialized = True
        logger.info(f"🛰️ 网关管理器已初始化：{summary}")
        return summary

    async def _upgrade_loop(self, name: str, gw, attempts: int = 24, interval: float = 5.0):
        """后台：网关处于 simulated 时，周期性重试真实连接，成功则自动切 live。

        上限 attempts*interval 秒（默认 24*5=120s）后停止重试，保持 simulated。
        """
        import asyncio as _asyncio
        for _ in range(attempts):
            await _asyncio.sleep(interval)
            try:
                if getattr(gw, "_mode", "simulated") == "simulated":
                    await gw.connect()
                    if getattr(gw, "_mode", "simulated") != "simulated":
                        logger.info(f"🛰️ 网关 {name} 已升级为 live 模式（{gw._mode}）")
                        break
            except Exception as e:
                logger.debug(f"网关 {name} 升级重试中：{e}")

    async def ensure_ready(self):
        """幂等：仅在尚未初始化时连接一次。

        兼容两种调用场景：① lifespan 已初始化；② 直接经 httpx ASGITransport
        （不触发 lifespan）调用 API 时，首次请求自动初始化，避免网关始终未就绪。
        """
        if not self._initialized:
            await self.initialize()
        return self._initialized

    async def health(self) -> dict:
        per = {}
        modes: dict[str, int] = {}
        ready = 0
        for name, gw in self._gateways.items():
            try:
                h = await gw.health_check()
            except Exception as e:
                h = {"name": name, "error": str(e)}
            per[name] = h
            if h.get("running"):
                ready += 1
            m = h.get("mode")
            if m:
                modes[m] = modes.get(m, 0) + 1
        return {
            "total": len(self._gateways),
            "ready": ready,
            "initialized": self._initialized,
            "modes": modes,
            "gateways": per,
        }

    def get(self, name: str):
        return self._gateways.get(name)

    async def get_for_tenant(self, tenant_id: str):
        """返回某租户的网关管理器：未配置则共享平台网关；已配置则返回隔离实例。

        Returns:
            (gw_manager, is_shared)
        """
        from src.runtime.tenant_store import tenant_store

        if tenant_id in ("default", None):
            return self, True
        cfg = tenant_store.get_gateway_config(tenant_id)
        if not cfg:
            return self, True
        if tenant_id not in self._tenant_managers:
            mgr = GatewayManager(overrides={**cfg, "_tenant_id": tenant_id})
            await mgr.initialize()
            self._tenant_managers[tenant_id] = mgr
        return self._tenant_managers[tenant_id], False

    async def read(self, name: str, address: str, count: int = 1) -> list[DataPoint]:
        gw = self._gateways.get(name)
        if not gw:
            raise KeyError(f"Unknown gateway: {name}")
        result = await gw.read(address, count)
        # 孪生体状态上行：每次读取即更新对应 holon 孪生体（全息孪生社会最小落地）
        try:
            await self.publish_to_twin_feed(result, source=name)
        except Exception:
            pass
        return result

    async def publish_to_twin_feed(self, datapoints, source: str | None = None) -> int:
        """把网关读到的数据点归一为 UNS 事件（gateway 路），由 UNS 内部路由到对应 holon 孪生体。

        这是「网关实时流进 agent 推理」的最小落地，且把五路感知的第一步（网关流）
        先归一进统一事件总线（轻量 UNS），再驱动孪生体状态上行；agent 后续推理可经
        BaseAgent.twin_context() 读取这份活镜像。韧性：UNS 路由失败静默降级，不阻断 read。
        """
        if not datapoints:
            return 0
        from collections import defaultdict
        grouped: dict[str, dict] = defaultdict(dict)
        for dp in datapoints:
            hk = getattr(dp, "holon_kind", "machine") or "machine"
            grouped[hk][dp.tag] = dp.value
        n = 0
        for hk, values in grouped.items():
            uns.publish(
                CHANNEL_GATEWAY,
                source or "gateway",
                "sensor_reading",
                payload=values,
                entities=[f"HOLON:{hk}"],
                route_holon=hk,
            )
            n += 1
        return n

    async def ingest_event(self, holon_kind: str, values: dict, source: str | None = None) -> int:
        """公开入口：外部/测试注入一条实时事件（模拟订阅流），经 UNS(system 路) 汇入孪生体状态。"""
        uns.publish(
            CHANNEL_SYSTEM,
            source or "external",
            "sensor_reading",
            payload=values,
            entities=[f"HOLON:{holon_kind}"],
            route_holon=holon_kind,
        )
        return 1

    async def disconnect_all(self):
        for gw in self._gateways.values():
            try:
                await gw.disconnect()
            except Exception:
                pass


# 进程级单例
manager = GatewayManager()
