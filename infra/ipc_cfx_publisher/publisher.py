"""IPC-CFX 事件发布器——向 RabbitMQ 的 cfx topic exchange 周期发布 CFX.* 事件。

让 IPC-CFX 网关在 live 模式下有真实事件流可消费（而非空 broker）。
事件主题/结构对齐 src/gateways/ipc_cfx/gateway.py 的 SIMULATED_TOPICS。
"""
import os
import asyncio
import json
import random
import logging

import aio_pika

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipc-cfx-publisher")

BROKER = os.getenv("RABBITMQ_URL", "amqp://rabbitmq:5672")

TOPICS = {
    "CFX.Production.TestResults": lambda: {
        "Source": "SMT-L01",
        "TestResult": random.choice(["Pass", "Fail", "Pass"]),
        "DefectCode": random.choice(["", "", "SOLDER_BRIDGE"]),
    },
    "CFX.ResourcePerformance.EquipmentStatusChanged": lambda: {
        "Source": random.choice(["scanner_1", "etcher_1", "aoi_1"]),
        "OldStatus": "Idle",
        "NewStatus": random.choice(["Active", "Active", "Maintenance"]),
    },
    "CFX.MaterialManagement.MaterialCarrierLoaded": lambda: {
        "Source": "SMT-L01",
        "CarrierId": f"MC-{random.randint(1000, 9999)}",
        "Material": random.choice(["PCB-0001", "二极管-0002", "三极管-0003"]),
    },
    "CFX.Production.AssemblyAndTest.WorkCompleted": lambda: {
        "Source": "SMT-L01",
        "UnitCount": random.randint(80, 130),
        "YieldPct": round(random.uniform(90.0, 99.5), 1),
    },
}


async def main():
    conn = await aio_pika.connect_robust(BROKER)
    channel = await conn.channel()
    exchange = await channel.declare_exchange("cfx", aio_pika.ExchangeType.TOPIC)
    logger.info("📤 IPC-CFX publisher -> %s (topics=%d)", BROKER, len(TOPICS))
    while True:
        for topic, gen in TOPICS.items():
            msg = gen()
            await exchange.publish(
                aio_pika.Message(body=json.dumps(msg, ensure_ascii=False).encode("utf-8")),
                routing_key=topic,
            )
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
