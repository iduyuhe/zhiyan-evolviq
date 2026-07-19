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

logger = logging.getLogger(__name__)


class GatewayManager:
    """统一网关管理器（单例语义，由 main lifespan 持有）"""

    def __init__(self):
        self._gateways = {
            "modbus": ModbusGateway(host=settings.modbus_host, port=settings.modbus_port),
            "mqtt": MQTTGateway(broker=settings.mqtt_broker, port=settings.mqtt_port),
            "opcua": OpcUaGateway(endpoint=settings.opcua_endpoint),
            "ipc_cfx": IpcCfxGateway(broker=settings.ipc_cfx_broker),
        }
        self._initialized = False

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

    async def read(self, name: str, address: str, count: int = 1) -> list[DataPoint]:
        gw = self._gateways.get(name)
        if not gw:
            raise KeyError(f"Unknown gateway: {name}")
        return await gw.read(address, count)

    async def disconnect_all(self):
        for gw in self._gateways.values():
            try:
                await gw.disconnect()
            except Exception:
                pass


# 进程级单例
manager = GatewayManager()
