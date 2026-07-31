"""OPC-UA ��议网关（V2 — 半导体晶圆厂设备模板库，2026-07-29）

连接 OPC-UA Server，读取半导体 Fab 设备节点（光刻机/刻蚀机/薄膜沉积/CMP/检测/离子注入）。
V2 扩展：6 大类 9 台设备全部预置 OPC-UA 标签映射；simulated 模式可漂移，live 模式直接读取。

"先建模板不等待签约"策略（杜总 2026-07-29 定调）：
- equipment_profiles.py 定义每个设备类型的标签模板
- 本网关按设备类型生成模拟节点
- 客户接入时，同型号设备直接套模板，数日即可接入
"""

import asyncio
import logging
import random
import time

from src.gateways.base import BaseGateway, DataPoint, GatewayConfig

logger = logging.getLogger(__name__)

# 模拟 OPC-UA 节点映射（NodeId 形如 ns=2;s=Line1.OvenTemp）
# V1（SMT 产线）：保留向后兼容
# V2（2026-07-29）：半导体晶圆厂 6 大类 9 台设备的传感器标签
# 每台设备的标签定义与 equipment_profiles.py 的 opcua_tags 字段同步。
SIMULATED_NODES = {
    # ── V1 向后兼容：SMT 产线 ──
    "ns=2;s=Line1.Status": {"type": "bool", "default": True},
    "ns=2;s=Line1.Throughput": {"type": "float", "min": 60.0, "max": 120.0, "default": 92.0},
    "ns=2;s=Line1.OvenTemp": {"type": "float", "min": 240.0, "max": 265.0, "default": 252.5},
    "ns=2;s=Line1.EnergyKw": {"type": "float", "min": 8.0, "max": 20.0, "default": 13.4},
    "ns=2;s=Line1.YieldPct": {"type": "float", "min": 90.0, "max": 99.9, "default": 97.3},

    # ── V2 半导体 Fab 设备 ──
    # 光刻机 × 2
    "ns=2;s=Scanner1.Status": {"type": "bool", "default": True},
    "ns=2;s=Scanner1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 88.0},
    "ns=2;s=Scanner1.LaserPower": {"type": "float", "min": 60.0, "max": 100.0, "default": 96.5},
    "ns=2;s=Scanner1.OverlayNm": {"type": "float", "min": 1.0, "max": 8.0, "default": 2.1},
    "ns=2;s=Scanner1.Vibration": {"type": "float", "min": 0.1, "max": 1.0, "default": 0.32},
    "ns=2;s=Scanner1.ChamberTemp": {"type": "float", "min": 20.0, "max": 26.0, "default": 22.4},
    "ns=2;s=Scanner1.PowerKw": {"type": "float", "min": 70.0, "max": 120.0, "default": 85.0},
    "ns=2;s=Scanner2.Status": {"type": "bool", "default": True},
    "ns=2;s=Scanner2.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 79.0},
    "ns=2;s=Scanner2.LaserPower": {"type": "float", "min": 60.0, "max": 100.0, "default": 82.0},
    "ns=2;s=Scanner2.OverlayNm": {"type": "float", "min": 1.0, "max": 8.0, "default": 3.5},
    "ns=2;s=Scanner2.Vibration": {"type": "float", "min": 0.1, "max": 1.0, "default": 0.45},
    "ns=2;s=Scanner2.ChamberTemp": {"type": "float", "min": 20.0, "max": 26.0, "default": 23.8},
    "ns=2;s=Scanner2.PowerKw": {"type": "float", "min": 70.0, "max": 120.0, "default": 88.0},

    # 刻蚀机 × 2
    "ns=2;s=Etcher1.Status": {"type": "bool", "default": True},
    "ns=2;s=Etcher1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 76.2},
    "ns=2;s=Etcher1.ChamberPressure": {"type": "float", "min": 20.0, "max": 80.0, "default": 45.8},
    "ns=2;s=Etcher1.RFPower": {"type": "float", "min": 800.0, "max": 2000.0, "default": 1480.0},
    "ns=2;s=Etcher1.EtchRate": {"type": "float", "min": 200.0, "max": 400.0, "default": 312.0},
    "ns=2;s=Etcher1.EtchRateDev": {"type": "float", "min": 0.0, "max": 15.0, "default": 3.2},
    "ns=2;s=Etcher1.PowerKw": {"type": "float", "min": 30.0, "max": 70.0, "default": 42.0},
    "ns=2;s=Etcher2.Status": {"type": "bool", "default": True},
    "ns=2;s=Etcher2.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 91.0},
    "ns=2;s=Etcher2.ChamberPressure": {"type": "float", "min": 20.0, "max": 80.0, "default": 38.2},
    "ns=2;s=Etcher2.RFPower": {"type": "float", "min": 800.0, "max": 2000.0, "default": 1650.0},
    "ns=2;s=Etcher2.EtchRate": {"type": "float", "min": 200.0, "max": 400.0, "default": 345.0},
    "ns=2;s=Etcher2.EtchRateDev": {"type": "float", "min": 0.0, "max": 15.0, "default": 1.8},
    "ns=2;s=Etcher2.PowerKw": {"type": "float", "min": 30.0, "max": 70.0, "default": 48.0},

    # 薄膜沉积 × 2
    "ns=2;s=Deposition1.Status": {"type": "bool", "default": True},
    "ns=2;s=Deposition1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 92.1},
    "ns=2;s=Deposition1.ChamberVacuum": {"type": "float", "min": 1e-8, "max": 1e-5, "default": 8e-7},
    "ns=2;s=Deposition1.HeaterTemp": {"type": "float", "min": 300.0, "max": 450.0, "default": 385.0},
    "ns=2;s=Deposition1.TargetErosion": {"type": "float", "min": 10.0, "max": 100.0, "default": 65.0},
    "ns=2;s=Deposition1.DepositionRate": {"type": "float", "min": 5.0, "max": 15.0, "default": 8.2},
    "ns=2;s=Deposition1.PowerKw": {"type": "float", "min": 35.0, "max": 85.0, "default": 55.0},
    "ns=2;s=Deposition2.Status": {"type": "bool", "default": True},
    "ns=2;s=Deposition2.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 73.5},
    "ns=2;s=Deposition2.ChamberVacuum": {"type": "float", "min": 1e-8, "max": 1e-5, "default": 5e-6},
    "ns=2;s=Deposition2.HeaterTemp": {"type": "float", "min": 300.0, "max": 450.0, "default": 400.0},
    "ns=2;s=Deposition2.RFPower": {"type": "float", "min": 200.0, "max": 600.0, "default": 350.0},
    "ns=2;s=Deposition2.DepositionRate": {"type": "float", "min": 5.0, "max": 20.0, "default": 12.5},
    "ns=2;s=Deposition2.PowerKw": {"type": "float", "min": 40.0, "max": 90.0, "default": 60.0},

    # CMP 化学机械抛光 × 1
    "ns=2;s=CMP1.Status": {"type": "bool", "default": True},
    "ns=2;s=CMP1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 85.0},
    "ns=2;s=CMP1.PadTemp": {"type": "float", "min": 25.0, "max": 45.0, "default": 32.0},
    "ns=2;s=CMP1.PadLife": {"type": "float", "min": 0.0, "max": 100.0, "default": 62.0},
    "ns=2;s=CMP1.SlurryFlow": {"type": "float", "min": 100.0, "max": 400.0, "default": 250.0},
    "ns=2;s=CMP1.DownForce": {"type": "float", "min": 1.0, "max": 5.0, "default": 2.5},
    "ns=2;s=CMP1.PowerKw": {"type": "float", "min": 15.0, "max": 40.0, "default": 25.0},

    # 检测/量测 × 1
    "ns=2;s=Inspection1.Status": {"type": "bool", "default": True},
    "ns=2;s=Inspection1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 93.5},
    "ns=2;s=Inspection1.LaserSource": {"type": "float", "min": 50.0, "max": 100.0, "default": 88.0},
    "ns=2;s=Inspection1.StagePrecision": {"type": "float", "min": 0.5, "max": 5.0, "default": 1.2},
    "ns=2;s=Inspection1.DetectionRate": {"type": "float", "min": 80.0, "max": 160.0, "default": 125.0},
    "ns=2;s=Inspection1.DefectSensitivity": {"type": "float", "min": 80.0, "max": 100.0, "default": 95.0},
    "ns=2;s=Inspection1.PowerKw": {"type": "float", "min": 10.0, "max": 25.0, "default": 15.0},

    # 离子注入 × 1
    "ns=2;s=Implant1.Status": {"type": "bool", "default": True},
    "ns=2;s=Implant1.Health": {"type": "float", "min": 0.0, "max": 100.0, "default": 81.0},
    "ns=2;s=Implant1.BeamCurrent": {"type": "float", "min": 5.0, "max": 25.0, "default": 12.5},
    "ns=2;s=Implant1.BeamEnergy": {"type": "float", "min": 50.0, "max": 500.0, "default": 180.0},
    "ns=2;s=Implant1.ChamberVacuum": {"type": "float", "min": 1e-8, "max": 1e-5, "default": 2e-6},
    "ns=2;s=Implant1.SourceLife": {"type": "float", "min": 0.0, "max": 100.0, "default": 58.0},
    "ns=2;s=Implant1.PowerKw": {"type": "float", "min": 45.0, "max": 115.0, "default": 72.0},
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
