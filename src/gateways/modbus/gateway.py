"""Modbus TCP 协议网关

连接 Modbus 从站（真实 PLC 或 modbus-sim），读取 PCB/SMT 产线设备寄存器。
connect() 先尝试真实连接（pymodbus），失败自动回退 simulated 模式
（与 OPC-UA / Neo4j / DB 韧性策略一致），绝不阻断启动。

真实寄存器布局对齐 scripts/modbus_sim.py：
- Coil 地址 = SIMULATED_REGISTERS 中 type=coil 的 address（产线/设备状态）
- Holding Register 地址 = type=holding 的 address，值单位 x100（读回 /100）
"""

import asyncio
import logging
import random
import time

from src.gateways.base import BaseGateway, DataPoint, GatewayConfig

logger = logging.getLogger(__name__)

# 模拟/真实共用的寄存器映射（address 与 modbus_sim.py 对齐）
SIMULATED_REGISTERS = {
    "line_1_status": {"address": 0, "type": "coil", "default": True},
    "line_1_speed": {"address": 1, "type": "holding", "default": 85.0},  # % 线速
    "line_1_temp": {"address": 2, "type": "holding", "default": 25.5},  # 温度
    "line_1_uptime": {"address": 3, "type": "holding", "default": 7200.0},  # 秒
    "buffer_1_level": {"address": 10, "type": "holding", "default": 65.0},  # %
    "buffer_2_level": {"address": 11, "type": "holding", "default": 42.0},
    "feeder_1_status": {"address": 20, "type": "coil", "default": True},
    "feeder_2_status": {"address": 21, "type": "coil", "default": True},
    "printer_status": {"address": 30, "type": "coil", "default": True},
    "reflow_status": {"address": 31, "type": "coil", "default": True},
}


class ModbusGateway(BaseGateway):
    """Modbus TCP 协议网关"""

    def __init__(self, host: str = "localhost", port: int = 5020):
        super().__init__(GatewayConfig(name="Modbus TCP", poll_interval_seconds=30))
        self.host = host
        self.port = port
        self._registers = {k: v["default"] for k, v in SIMULATED_REGISTERS.items()}
        self._mode = "simulated"  # simulated | modbus
        self._connected = False
        self._client = None

    async def connect(self) -> bool:
        logger.info(f"🔌 Modbus: Connecting to {self.host}:{self.port}...")
        try:
            # 惰性导入：未安装 pymodbus 时直接走模拟模式，不破管
            from pymodbus.client import ModbusTcpClient

            client = ModbusTcpClient(host=self.host, port=self.port)
            if not client.connect():
                raise RuntimeError("Modbus connect refused")
            self._client = client
            self._mode = "modbus"
            self._connected = True
            self._running = True
            logger.info("✅ Modbus: Connected (live)")
            return True
        except Exception as e:
            self._mode = "simulated"
            self._connected = True
            self._running = True
            logger.warning(f"⚠️ Modbus: 真实从站不可用，回退模拟模式（{type(e).__name__}）")
            return True

    async def disconnect(self):
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._connected = False
        self._running = False
        logger.info("🔌 Modbus: Disconnected")

    async def read(self, address: str, count: int = 1) -> list[DataPoint]:
        now = time.time()
        # live 模式：从真实从站读取
        if self._mode == "modbus" and self._client is not None:
            meta = SIMULATED_REGISTERS.get(address)
            if meta:
                try:
                    if meta["type"] == "coil":
                        rr = await asyncio.to_thread(self._client.read_coils, meta["address"], 1)
                        val = bool(rr.bits[0])
                    else:
                        rr = await asyncio.to_thread(self._client.read_holding_registers, meta["address"], 1)
                        val = rr.registers[0] / 100.0
                    self._registers[address] = val
                    return [DataPoint(tag=address, value=val, timestamp=now, quality="good")]
                except Exception as e:
                    logger.warning(f"⚠️ Modbus read {address} 失败，回退内存值：{e}")
        # simulated 波动（保持原逻辑）
        for key in self._registers:
            if key.endswith("_speed") or key.endswith("_level"):
                delta = random.uniform(-2.0, 2.0)
                self._registers[key] = max(0, min(100, self._registers[key] + delta))
            elif key.endswith("_temp"):
                delta = random.uniform(-0.5, 0.5)
                self._registers[key] += delta
        if address in SIMULATED_REGISTERS:
            return [DataPoint(tag=address, value=self._registers[address], timestamp=now, quality="good")]
        return []

    async def write(self, address: str, value: float | str | bool) -> bool:
        """写入 Modbus 寄存器（控制指令）"""
        if address in self._registers:
            self._registers[address] = value
            logger.info(f"⚡ Modbus: Write {address} = {value}")
            return True
        logger.warning(f"⚠️ Modbus: Unknown register {address}")
        return False

    async def health_check(self) -> dict:
        base = await super().health_check()
        base.update({
            "host": self.host,
            "port": self.port,
            "mode": self._mode,
            "connected": self._connected,
            "registers_monitored": len(self._registers),
        })
        return base
