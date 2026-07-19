"""Modbus TCP模拟器——模拟PLC设备数据

运行：python scripts/modbus_sim.py
通过Modbus TCP协议在端口5020提供模拟数据。
"""

import logging
import random
import time

from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.server import StartTcpServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("modbus-sim")


def run_sim():
    """启动Modbus模拟器"""
    # 初始化寄存器数据
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [True] * 50),      # Digital Input
        co=ModbusSequentialDataBlock(0, [True] * 50),      # Coil
        hr=ModbusSequentialDataBlock(0, [8500] * 50),      # Holding Register (x100)
        ir=ModbusSequentialDataBlock(0, [2500] * 50),      # Input Register (x100)
    )
    context = ModbusServerContext(slaves=store, single=True)

    logger.info("🏭 Modbus 模拟器启动 on port 5020")
    logger.info("  模拟SMT产线PLC设备")
    logger.info("  Holding Registers: 线速85%, 温度25.5°C, 工时7200s")
    logger.info("  Coils: 产线状态=True, Feeder1=True, Feeder2=True")

    # 启动服务器（会阻塞）
    StartTcpServer(context=context, address=("0.0.0.0", 5020))


if __name__ == "__main__":
    run_sim()
