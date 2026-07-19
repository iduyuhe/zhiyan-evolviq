"""IPC-CFX 协议网关（V1）

IPC-CFX（IPC-2591）以 AMQP 1.0 消息总线承载制造事件（测试良率/设备状态/物料装载等）。
connect() 先尝试真实连接 aio-pika（AMQP Broker，如 RabbitMQ），失败自动回退 simulated 模式，
事件在本地缓存，绝不阻断启动（与 db.py / neo4j_client 韧性策略一致）。
"""

import asyncio
import json
import logging
import random
import time

from src.gateways.base import BaseGateway, DataPoint, GatewayConfig

logger = logging.getLogger(__name__)

# 模拟 IPC-CFX 事件主题（CFX.* 命名空间）
SIMULATED_TOPICS = {
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


class IpcCfxGateway(BaseGateway):
    """IPC-CFX 协议网关"""

    def __init__(self, broker: str = "amqp://localhost:5672"):
        super().__init__(GatewayConfig(name="IPC-CFX", poll_interval_seconds=10))
        self.broker = broker
        self._subscribed: list[str] = []
        self._message_cache: dict[str, DataPoint] = {}
        self._mode = "simulated"  # simulated | amqp
        self._connected = False
        self._connection = None
        self._channel = None
        self._exchange = None
        self._queue = None

    async def _on_message(self, message):
        try:
            async with message.process():
                body = message.body
                try:
                    value = json.loads(body)
                except Exception:
                    value = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else body
                topic = message.routing_key
                self._message_cache[topic] = DataPoint(
                    tag=topic, value=value, timestamp=time.time(), quality="good"
                )
        except Exception as e:
            logger.warning(f"⚠️ IPC-CFX on_message 处理失败：{e}")

    async def connect(self) -> bool:
        logger.info(f"🔌 IPC-CFX: Connecting to {self.broker}...")
        try:
            # 惰性导入：未安装 aio-pika 时直接走模拟模式，不破管
            import aio_pika

            connection = await aio_pika.connect_robust(self.broker)
            channel = await connection.channel()
            exchange = await channel.declare_exchange("cfx", aio_pika.ExchangeType.TOPIC)
            queue = await channel.declare_queue("", exclusive=True)
            for topic in SIMULATED_TOPICS:
                await queue.bind(exchange, routing_key=topic)
            await queue.consume(self._on_message)
            self._connection = connection
            self._channel = channel
            self._exchange = exchange
            self._queue = queue
            self._mode = "amqp"
            self._connected = True
            self._running = True
            logger.info("✅ IPC-CFX: Connected (live)")
            return True
        except Exception as e:
            self._mode = "simulated"
            self._connected = True
            self._running = True
            for topic in SIMULATED_TOPICS:
                self._subscribed.append(topic)
                self._message_cache[topic] = self._generate_message(topic)
            logger.warning(f"⚠️ IPC-CFX: Broker 不可用，回退模拟模式（{type(e).__name__}）")
            return True

    async def disconnect(self):
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = None
            self._channel = None
            self._exchange = None
            self._queue = None
        self._connected = False
        self._running = False
        logger.info("🔌 IPC-CFX: Disconnected")

    async def subscribe(self, topic: str):
        if self._channel is not None and self._exchange is not None:
            try:
                await self._queue.bind(self._exchange, routing_key=topic)
            except Exception:
                pass
        if topic not in self._subscribed:
            self._subscribed.append(topic)
            self._message_cache[topic] = self._generate_message(topic)
        logger.info(f"📡 IPC-CFX: Subscribed to {topic}")

    async def read(self, address: str, count: int = 1) -> list[DataPoint]:
        """读取 IPC-CFX 事件（live 模式取 broker 缓存，simulated 模式本地刷新）"""
        if self._mode == "amqp" and self._connection is not None:
            if address in self._message_cache:
                return [self._message_cache[address]]
            if address == "*":
                return list(self._message_cache.values())[:count]
            return []
        for topic in self._subscribed:
            if random.random() < 0.4:
                self._message_cache[topic] = self._generate_message(topic)
        if address in self._message_cache:
            return [self._message_cache[address]]
        if address == "*":
            return list(self._message_cache.values())[:count]
        return []

    async def publish(self, topic: str, message: dict) -> bool:
        """发布 IPC-CFX 事件（CFX.* 命名空间）"""
        logger.info(f"📤 IPC-CFX: Publish {topic}")
        if self._channel is not None and self._exchange is not None:
            try:
                payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
                await self._exchange.publish(aio_pika.Message(body=payload), routing_key=topic)
            except Exception as e:
                logger.warning(f"⚠️ IPC-CFX publish 失败：{e}")
        self._message_cache[topic] = DataPoint(tag=topic, value=message, timestamp=time.time(), quality="good")
        return True

    async def write(self, address: str, value: float | str | bool) -> bool:
        """IPC-CFX 写语义 = 发布事件（value 应为 dict 消息；非 dict 时包装为 {"value": value}）"""
        message = value if isinstance(value, dict) else {"value": value}
        return await self.publish(address, message)

    def _generate_message(self, topic: str) -> DataPoint:
        gen = SIMULATED_TOPICS.get(topic, lambda: {"note": "generic"})
        return DataPoint(tag=topic, value=gen(), timestamp=time.time(), quality="good")

    async def health_check(self) -> dict:
        base = await super().health_check()
        base.update({
            "broker": self.broker,
            "mode": self._mode,
            "connected": self._connected,
            "subscribed_topics": len(self._subscribed),
        })
        return base
