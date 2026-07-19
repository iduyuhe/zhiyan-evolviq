"""OPC-UA Server（准真实数据源）——供 OPC-UA 网关 live 模式消费。

暴露 ns=2 命名空间下的产线设备节点（与 src/gateways/opcua/gateway.py 的
SIMULATED_NODES 一一对应），并周期小幅波动，模拟真实设备数据。
监听 opc.tcp://0.0.0.0:4840。
"""
import asyncio
import logging
import random

from asyncua import Server, ua

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("opcua-server")

# (node_id, 类型, 初值, 下界, 上界) ；bool 类型无波动
NODES = [
    ("ns=2;s=Line1.Status", ua.VariantType.Boolean, True, None, None),
    ("ns=2;s=Line1.Throughput", ua.VariantType.Float, 92.0, 60.0, 120.0),
    ("ns=2;s=Line1.OvenTemp", ua.VariantType.Float, 252.5, 240.0, 265.0),
    ("ns=2;s=Line1.EnergyKw", ua.VariantType.Float, 13.4, 8.0, 20.0),
    ("ns=2;s=Line1.YieldPct", ua.VariantType.Float, 97.3, 90.0, 99.9),
    ("ns=2;s=Equip.Scanner1.Health", ua.VariantType.Float, 88.0, 0.0, 100.0),
    ("ns=2;s=Equip.Etcher1.Health", ua.VariantType.Float, 81.0, 0.0, 100.0),
    ("ns=2;s=Equip.Aoi1.Health", ua.VariantType.Float, 76.0, 0.0, 100.0),
]


async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    # 确保命名空间 2 存在（第一个自定义命名空间），与网关 ns=2 对齐
    await server.register_namespace("http://zhiyan.evolviq/opcua")

    state = {}
    for ident, vtype, val, lo, hi in NODES:
        ns = int(ident.split(";")[0].split("=")[1])
        s = ident.split(";")[1].split("=")[1]
        nodeid = ua.NodeId(s, ns)
        var = await server.nodes.objects.add_variable(nodeid, s, val, varianttype=vtype)
        await var.set_writable()
        state[ident] = (var, lo, hi, val)

    logger.info("🏭 OPC-UA Server 启动 opc.tcp://0.0.0.0:4840 (ns=2, %d 节点)", len(NODES))

    await server.start()
    try:
        while True:
            await asyncio.sleep(5)
            for ident, (var, lo, hi, val) in state.items():
                if lo is None:
                    continue
                nv = max(lo, min(hi, val + random.uniform(-1, 1) * (hi - lo) * 0.01))
                state[ident] = (var, lo, hi, nv)
                try:
                    await var.write_value(nv)
                except Exception as e:
                    logger.warning(f"write {ident} 失败: {e}")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
