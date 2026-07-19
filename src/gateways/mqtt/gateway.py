"""MQTT 协议网关

连接 MQTT Broker，订阅 SMT 产线设备数据主题。
connect() 先尝试真实连接（paho-mqtt），失败自动回退 simulated 模式
（与 OPC-UA / Neo4j / DB 韧性策略一致），绝不阻断启动。
真实模式下，数据来自 broker 上的发布者（如工厂数据仿真服务）。
"""

import asyncio
import json
import logging
import random
import time

from src.gateways.base import BaseGateway, DataPoint, GatewayConfig

logger = logging.getLogger(__name__)

SIMULATED_TOPICS = {
    "factory/line1/temperature": {"type": "float", "min": 22.0, "max": 28.0},
    "factory/line1/humidity": {"type": "float", "min": 40.0, "max": 60.0},
    "factory/line1/production_rate": {"type": "float", "min": 70.0, "max": 98.0},
    "factory/line1/defect_rate": {"type": "float", "min": 0.1, "max": 3.0},
    "factory/line1/process_count": {"type": "int", "min": 1000, "max": 5000},
    "factory/buffer/main/level": {"type": "int", "min": 20, "max": 90},
    "factory/quality/solder_paste": {"type": "str", "values": ["ok", "warning", "alarm"]},
}


class MQTTGateway(BaseGateway):
    """MQTT 协议网关"""

    def __init__(self, broker: str = "localhost", port: int = 1883):
        super().__init__(GatewayConfig(name="MQTT Gateway", poll_interval_seconds=10))
        self.broker = broker
        self.port = port
        self._subscribed_topics: list[str] = []
        self._message_cache: dict[str, DataPoint] = {}
        self._mode = "simulated"  # simulated | mqtt
        self._connected = False
        self._client = None

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload
            try:
                value = json.loads(payload)
            except Exception:
                value = payload.decode("utf-8", "replace") if isinstance(payload, (bytes, bytearray)) else payload
            self._message_cache[msg.topic] = DataPoint(
                tag=msg.topic, value=value, timestamp=time.time(), quality="good"
            )
        except Exception as e:
            logger.warning(f"⚠️ MQTT on_message 解析失败：{e}")

    async def connect(self) -> bool:
        logger.info(f"🔌 MQTT: Connecting to {self.broker}:{self.port}...")
        try:
            # 惰性导入：未安装 paho-mqtt 时直接走模拟模式，不破管
            import paho.mqtt.client as mqtt

            try:
                kwargs = {"callback_api_version": mqtt.CallbackAPIVersion.VERSION2}
            except AttributeError:
                kwargs = {}
            client = mqtt.Client(**kwargs, client_id="zhiyan-runtime")
            client.on_connect = lambda c, u, f, *a: [c.subscribe(t) for t in SIMULATED_TOPICS]
            client.on_message = self._on_message
            client.connect(self.broker, self.port, keepalive=60)
            client.loop_start()
            self._client = client
            self._mode = "mqtt"
            self._connected = True
            self._running = True
            logger.info("✅ MQTT: Connected (live)")
            return True
        except Exception as e:
            self._mode = "simulated"
            self._connected = True
            self._running = True
            for topic, config in SIMULATED_TOPICS.items():
                self._message_cache[topic] = self._generate_mock_data(topic, config)
                self._subscribed_topics.append(topic)
            logger.warning(f"⚠️ MQTT: Broker 不可用，回退模拟模式（{type(e).__name__}）")
            return True

    async def disconnect(self):
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._connected = False
        self._running = False
        logger.info("🔌 MQTT: Disconnected")

    async def subscribe(self, topic: str):
        if self._client is not None:
            try:
                self._client.subscribe(topic)
            except Exception:
                pass
        if topic not in self._subscribed_topics:
            self._subscribed_topics.append(topic)
        logger.info(f"📡 MQTT: Subscribed to {topic}")

    async def read(self, address: str, count: int = 1) -> list[DataPoint]:
        # live 模式：从 broker 缓存取（由 _on_message 填充）
        if self._mode == "mqtt" and self._client is not None:
            if address in self._message_cache:
                return [self._message_cache[address]]
            if address == "*":
                return list(self._message_cache.values())[:count]
            return []
        # simulated 波动
        for topic, config in SIMULATED_TOPICS.items():
            if random.random() < 0.3:
                self._message_cache[topic] = self._generate_mock_data(topic, config)
        if address in self._message_cache:
            return [self._message_cache[address]]
        if address == "*":
            return list(self._message_cache.values())[:count]
        return []

    async def write(self, address: str, value) -> bool:
        """发布 MQTT 消息"""
        logger.info(f"📤 MQTT: Publish {address} = {value}")
        if self._client is not None:
            try:
                payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                self._client.publish(address, payload)
            except Exception as e:
                logger.warning(f"⚠️ MQTT publish 失败：{e}")
        self._message_cache[address] = DataPoint(tag=address, value=value, timestamp=time.time(), quality="good")
        return True

    def _generate_mock_data(self, topic, config):
        if config["type"] == "float":
            value = round(random.uniform(config["min"], config["max"]), 1)
        elif config["type"] == "int":
            value = random.randint(config["min"], config["max"])
        else:
            value = random.choice(config["values"])
        return DataPoint(tag=topic, value=value, timestamp=time.time(), quality="good")

    async def health_check(self) -> dict:
        base = await super().health_check()
        base.update({
            "broker": self.broker,
            "port": self.port,
            "mode": self._mode,
            "connected": self._connected,
            "subscribed_topics": len(self._subscribed_topics),
        })
        return base
