"""OPC-UA 协议网关（V1）

连接 OPC-UA Server，读取半导体/SMT 产线设备节点（温度/线速/能耗/良率/设备健康）。
MVP/V1 沙箱无真实 OPC-UA Server，故 connect() 惰性导入 asyncua，失败时自动回退
simulated 模式（与 db.py / neo4j_client 韧性策略一致），绝不阻断启动。
"""

import asyncio
import logging
import random
import time

from src.gateways.base import BaseGateway, DataPoint, GatewayConfig

logger = logging.getLogger(__name__)

# 模拟 OPC-UA 节点映射（NodeId 形如 ns=2;s=Line1.OvenTemp）
SIMULATED_NODES = {
    "ns=2;s=Line1.Status": {"type": "bool", "default": True},
    "ns=2;s=Line1.Throughput": {"type": "float", "min": 60.0, "max": 120.0, "default": 92.0},  # 板/分钟
    "ns=2;s=Line1.OvenTemp": {"type": "float", "min": 240.0, "max": 265.0, "default": 252.5},  # ℃
    "ns=2;s=Line1.EnergyKw": {"type": "float", "min": 8.0, "max": 20.0, "default": 13.4},  # kW
    "ns=2;s=Line1.YieldPct": {"type": "float", "min": 90.0, "max": 99.9, "default": 97.3},  # %
    "ns=2;s=Equip.Scanner1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 88.0},
    "ns=2;s=Equip.Etcher1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 81.0},
    "ns=2;s=Equip.Aoi1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 76.0},
}


class OpcUaGateway(BaseGateway):
    """OPC-UA 协议网关"""

    def __init__(self, endpoint: str = "opc.tcp://localhost:4840"):
        super().__init__(GatewayConfig(name="OPC-UA", poll_interval_seconds=15))
        self.endpoint = endpoint
        self._values = {k: v["default"] for k, v in SIMULATED_NODES.items()}
        self._mode = "simulated"  # simulated | opcua
        self._connected = False
        self._client = None

    async def connect(self) -> bool:
        logger.info(f"🔌 OPC-UA: Connecting to {self.endpoint}...")
        try:
            # 惰性导入：沙箱未安装 asyncua 时直接走模拟模式，不破管
            from asyncua import Client  # type: ignore

            client = Client(self.endpoint)
            await client.connect()
            self._client = client
            self._mode = "opcua"
            self._connected = True
            self._running = True
            logger.info("✅ OPC-UA: Connected (live server)")
            return True
        except Exception as e:
            self._mode = "simulated"
            self._connected = True  # 模拟模式下视为"已就绪"
            self._running = True
            logger.warning(f"⚠️ OPC-UA: 真实 Server 不可用，回退模拟模式（{type(e).__name__}）")
            return True

    async def disconnect(self):
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._connected = False
        self._running = False
        logger.info("🔌 OPC-UA: Disconnected")

    async def read(self, address: str, count: int = 1) -> list[DataPoint]:
        """读取 OPC-UA 节点数据。

        live 模式（已连真实 Server）：直接读真实节点值，失败回退本地值；
        模拟模式：本地波动。
        """
        now = time.time()
        # live 模式：从真实 Server 读取（失败回退本地值 + 记日志）
        if self._mode == "opcua" and self._client is not None:
            if address in self._values or address == "*":
                addrs = [address] if address != "*" else list(self._values.keys())
                points = []
                for a in addrs[:count] if address == "*" else addrs:
                    try:
                        node = self._client.get_node(a)
                        val = await asyncio.to_thread(node.read_value)
                        self._values[a] = val
                        points.append(DataPoint(tag=a, value=val, timestamp=now, quality="good"))
                    except Exception as e:
                        logger.warning(f"⚠️ OPC-UA 读 {a} 失败，回退本地值：{e}")
                        points.append(DataPoint(tag=a, value=self._values.get(a), timestamp=now, quality="bad"))
                return points
            return []
        # 模拟波动（仅对数值型）
        for key in self._values:
            meta = SIMULATED_NODES[key]
            if meta["type"] == "float":
                lo, hi = meta["min"], meta["max"]
                delta = (hi - lo) * 0.01 * random.uniform(-1, 1)
                self._values[key] = max(lo, min(hi, self._values[key] + delta))
        if address in self._values:
            return [DataPoint(tag=address, value=self._values[address], timestamp=now, quality="good")]
        if address == "*":
            return [DataPoint(tag=k, value=v, timestamp=now, quality="good") for k, v in list(self._values.items())[:count]]
        return []

    async def write(self, address: str, value: float | str | bool) -> bool:
        """写入 OPC-UA 节点（控制指令）"""
        if address in self._values:
            self._values[address] = value
            logger.info(f"⚡ OPC-UA: Write {address} = {value}")
            return True
        logger.warning(f"⚠️ OPC-UA: Unknown node {address}")
        return False

    async def health_check(self) -> dict:
        base = await super().health_check()
        base.update({
            "endpoint": self.endpoint,
            "mode": self._mode,
            "connected": self._connected,
            "nodes_monitored": len(self._values),
        })
        return base
