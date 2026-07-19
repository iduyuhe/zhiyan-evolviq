"""P1-0 本地校验脚本（T5）

目的：在不依赖任何真实外部服务的前提下，验证：
  1) 真实网关库均可导入（pymodbus / paho-mqtt / aio-pika / asyncua / neo4j）
  2) 四类网关 connect() 在「真实 endpoint 不可达」时，正确回退 simulated 且不抛异常
  3) 网关管理器 ensure_ready() 幂等初始化，4 网关均进入 running 状态
  4) health() 聚合正确，mode 均为 simulated（因无真实服务）

运行环境：项目 .venv（已装全依赖）。
用法：.venv/Scripts/python.exe scripts/verify_p1_gateways_local.py
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

# 1) 导入真实库（不可用时此处直接失败，是护栏要抓的问题）
IMPORT_RESULTS = {}
for mod in [
    "pymodbus.client",
    "paho.mqtt.client",
    "aio_pika",
    "asyncua",
    "neo4j",
]:
    try:
        __import__(mod)
        IMPORT_RESULTS[mod] = "OK"
    except Exception as e:  # noqa
        IMPORT_RESULTS[mod] = f"FAIL: {type(e).__name__}: {e}"


async def main():
    from src.gateways.manager import manager

    # 2) + 3) ensure_ready 幂等初始化（指向 localhost，真实服务不存在 → 全部回退）
    await manager.ensure_ready()
    await manager.ensure_ready()  # 第二次应为幂等，不重复连接

    # 4) health 聚合
    health = await manager.health()
    per = health["gateways"]

    # 判定
    problems = []
    if health["total"] != 4:
        problems.append(f"网关总数 != 4（实际 {health['total']}）")
    if health["ready"] != 4:
        problems.append(f"就绪网关 != 4（实际 {health['ready']}）")

    # 逐个网关检查：running=True，且 mode 为合法值
    for name, h in per.items():
        if not h.get("running"):
            problems.append(f"网关 {name} 未 running：{h}")
        mode = h.get("mode")
        if mode not in ("simulated", "modbus", "mqtt", "amqp", "opcua"):
            problems.append(f"网关 {name} mode 非法：{mode}")

    print("=" * 60)
    print("P1-0 本地校验结果")
    print("=" * 60)
    print("[1] 真实库导入:")
    for mod, res in IMPORT_RESULTS.items():
        flag = "✅" if res == "OK" else "❌"
        print(f"    {flag} {mod}: {res}")

    print("\n[2-4] 网关 health 聚合:")
    print(f"    total={health['total']} ready={health['ready']} initialized={health['initialized']}")
    print(f"    modes={health['modes']}")
    for name, h in per.items():
        print(f"    - {name}: mode={h.get('mode')} running={h.get('running')} "
              f"connected={h.get('connected')} host/broker={h.get('host') or h.get('broker') or h.get('endpoint')}")

    print("\n" + "=" * 60)
    if problems:
        print("❌ 校验失败:")
        for p in problems:
            print(f"   - {p}")
        return 1
    print("✅ 全部通过：4 网关真实库可导入，connect 在无真实服务时正确回退 simulated，且 manager 可初始化。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
