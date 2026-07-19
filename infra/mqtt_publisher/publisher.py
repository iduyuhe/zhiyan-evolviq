"""MQTT 工厂数据发布器——向 mosquitto 周期发布 factory/line1/* 主题。

让 MQTT 网关在 live 模式下有真实数据流可消费（而非空 broker）。
主题/取值与 src/gateways/mqtt/gateway.py 的 SIMULATED_TOPICS 对齐。
"""
import os
import time
import json
import random
import logging

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqtt-publisher")

BROKER = os.getenv("MOSQUITTO_HOST", "mosquitto")
PORT = int(os.getenv("MOSQUITTO_PORT", "1883"))

TOPICS = {
    "factory/line1/temperature": ("float", 22.0, 28.0),
    "factory/line1/humidity": ("float", 40.0, 60.0),
    "factory/line1/production_rate": ("float", 70.0, 98.0),
    "factory/line1/defect_rate": ("float", 0.1, 3.0),
    "factory/line1/process_count": ("int", 1000, 5000),
    "factory/buffer/main/level": ("int", 20, 90),
    "factory/quality/solder_paste": ("str", ["ok", "warning", "alarm"]),
}


def gen_value(spec):
    kind = spec[0]
    if kind == "str":
        # 规格形如 ("str", [choices]) —— 仅 2 元素
        return random.choice(spec[1])
    a, b = spec[1], spec[2]
    if kind == "float":
        return round(random.uniform(a, b), 1)
    return random.randint(int(a), int(b))


def main():
    try:
        kwargs = {"callback_api_version": mqtt.CallbackAPIVersion.VERSION2}
    except AttributeError:
        kwargs = {}
    client = mqtt.Client(**kwargs, client_id="zhiyan-mqtt-pub")
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    logger.info("📡 MQTT publisher -> %s:%d (topics=%d)", BROKER, PORT, len(TOPICS))
    while True:
        for topic, spec in TOPICS.items():
            client.publish(topic, json.dumps(gen_value(spec)))
        time.sleep(5)


if __name__ == "__main__":
    main()
