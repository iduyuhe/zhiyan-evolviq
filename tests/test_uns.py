"""T5 UNS 五路归一单元测试（v30 六路：新增 environment 第⑥路 + credibility 字段）

验证：
1. 五路事件同 schema 归一入总线，各 channel 可查可回溯
2. gateway 路事件经 UNS 自动路由到孪生体（twin_feed）
3. collab 源正确标注 channel + entities（设备作为一等参与者）
4. 韧性降级：twin_feed 不可达时 UNS.publish 不抛、非路由事件照常入库
5. environment 第⑥路 + credibility 字段（F4 可信治理）
"""

import pytest
from src.runtime.uns import (
    UnifiedNamespace,
    CHANNEL_GATEWAY,
    CHANNEL_SYSTEM,
    CHANNEL_HUMAN,
    CHANNEL_SOCIAL,
    CHANNEL_MEETING,
    CHANNEL_COLLAB,
    CHANNEL_ENVIRONMENT,
    CRED_OFFICIAL,
    CREDIBILITY_LEVELS,
)
from src.runtime.data_sources.registry import registry as ds_registry
from src.runtime.data_sources.connectors.energy_twin import EnergyTwinDataSource


@pytest.fixture
def uns_inst():
    u = UnifiedNamespace()
    ds = EnergyTwinDataSource(tenant_id="default")
    ds_registry.register(ds)
    yield u, ds


def test_five_channel_normalization(uns_inst):
    u, _ = uns_inst
    u.publish_gateway("opcua://line-3", {"energy_kwh__L1": 100.0})
    u.publish_system("erp://sap/mm", {"doc": "PO123"})
    u.publish_human("wecom://zhang", {"note": "供应商交期风险"})
    u.publish_social("email://proc", {"thread": "price"})
    u.publish_meeting("meet://strategy", {"topic": "Q3"})
    u.publish_collab("collab://community-equipment", {"msg": "液压机建议维护"}, entities=["DEV:hyd-105"])
    u.publish_environment("env://policy/miit", {"title": "新标准"}, entities=["POLICY:标准"],
                          credibility=CRED_OFFICIAL)
    counts = u.channel_counts()
    assert counts[CHANNEL_GATEWAY] == 1
    assert counts[CHANNEL_SYSTEM] == 1
    assert counts[CHANNEL_HUMAN] == 1
    assert counts[CHANNEL_SOCIAL] == 1
    assert counts[CHANNEL_MEETING] == 1
    assert counts[CHANNEL_COLLAB] == 1
    assert counts[CHANNEL_ENVIRONMENT] == 1


def test_gateway_routes_to_twin(uns_inst):
    u, ds = uns_inst
    u.publish_gateway(
        "opcua://line-3",
        {"energy_kwh__SMT-L01": 51000.0, "green_ratio__SMT-L01": 33.0},
    )
    # 结构化状态应已上行到孪生体
    assert ds.twin_state["values"].get("energy_kwh__SMT-L01") == 51000.0
    assert ds.twin_state["values"].get("green_ratio__SMT-L01") == 33.0
    # 事件可查，channel/source 正确
    evs = u.query(channel=CHANNEL_GATEWAY)
    assert evs[-1]["channel"] == CHANNEL_GATEWAY
    assert evs[-1]["source"] == "opcua://line-3"


def test_system_event_with_explicit_holon_routes(uns_inst):
    u, ds = uns_inst
    # system 路带显式 holon 标注（非 machine 前缀键），也应路由到 machine 孪生体
    u.publish_system(
        "mqtt://plc-7",
        {"energy_kwh__SMT-L02": 47000.0},
        route_holon="machine",
    )
    assert ds.twin_state["values"].get("energy_kwh__SMT-L02") == 47000.0


def test_collab_source_tagged(uns_inst):
    u, _ = uns_inst
    u.publish_collab(
        "collab://community-equipment",
        {"msg": "液压机建议维护", "suggest": "更换密封件"},
        entities=["DEV:hyd-105", "LINE:3"],
    )
    ev = u.query(channel=CHANNEL_COLLAB)[-1]
    assert ev["channel"] == CHANNEL_COLLAB
    assert "DEV:hyd-105" in ev["entities"]
    assert ev["type"] == "collab_message"
    # collab 路不应路由到孪生体（非 gateway/system）
    assert "energy_kwh__" not in ev["payload"]


def test_non_routeable_channels_not_routed(uns_inst):
    u, ds = uns_inst
    before = dict(ds.twin_state["values"])
    u.publish_human("wecom://zhang", {"note": "设备异响"})
    u.publish_social("email://x", {"thread": "供应商"})
    u.publish_meeting("meet://y", {"topic": "复盘"})
    # 三路不应写入孪生体
    assert ds.twin_state["values"] == before


def test_resilience_twin_unreachable(uns_inst, monkeypatch):
    u, _ = uns_inst
    # 破坏 registry.route_event，验证 UNS.publish 不抛（韧性降级）
    def boom(*a, **k):
        raise RuntimeError("twin feed down")

    monkeypatch.setattr(ds_registry, "route_event", boom)
    ev = u.publish_gateway("opcua://line-3", {"energy_kwh__SMT-L01": 1.0})
    assert ev.channel == CHANNEL_GATEWAY
    # 非路由事件照常入库
    u.publish_human("wecom://x", {"note": "hi"})
    assert u.channel_counts()[CHANNEL_HUMAN] == 1


def test_query_filter_and_recent(uns_inst):
    u, _ = uns_inst
    for i in range(5):
        u.publish_gateway(f"opcua://line-{i}", {"energy_kwh__L{i}": float(i)})
    assert len(u.query(channel=CHANNEL_GATEWAY)) == 5
    assert len(u.query(n=3)) == 3
    assert len(u.recent(2)) == 2


# ---------------- P1⑤ 并发安全对抗测试 ----------------

def test_concurrent_publish_no_loss_p1():
    """多线程并发 publish：不丢事件、不抛异常、计数精确（RLock + deque 原子性）。"""
    import threading

    u = UnifiedNamespace(maxlen=100000)
    n_threads, n_per = 8, 200
    errors: list[Exception] = []

    def worker(tid: int):
        try:
            for i in range(n_per):
                u.publish_human(f"wecom://t{tid}", {"note": f"msg-{tid}-{i}"})
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert u.channel_counts()[CHANNEL_HUMAN] == n_threads * n_per


def test_concurrent_subscribe_publish_p1():
    """publish 与 subscribe 并发交错：订阅者列表不被破坏，已注册 handler 全部收到后续事件。"""
    import threading

    u = UnifiedNamespace(maxlen=100000)
    received = []
    lock = threading.Lock()

    def make_handler(hid: int):
        def h(ev):
            with lock:
                received.append((hid, ev.id))
        return h

    stop = threading.Event()

    def subscriber_worker():
        for i in range(50):
            u.subscribe(CHANNEL_SOCIAL, make_handler(i))
        stop.set()

    def publisher_worker():
        while not stop.is_set():
            u.publish_social("email://x", {"n": 1})
        # stop 后再发一批，此时 50 个 handler 已全部注册
        for _ in range(10):
            u.publish_social("email://x", {"n": 2})

    ts = [threading.Thread(target=subscriber_worker), threading.Thread(target=publisher_worker)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    # stop 后发布的 10 条，每条应被全部 50 个 handler 收到
    tail_counts: dict[int, int] = {}
    for hid, _ in received:
        tail_counts[hid] = tail_counts.get(hid, 0) + 1
    # 每个 handler 至少收到 stop 后的 10 条
    assert all(tail_counts.get(i, 0) >= 10 for i in range(50))


def test_ring_buffer_maxlen_under_concurrency_p1():
    """环形淘汰在并发下依然守 maxlen 上限（deque 原子淘汰，绝不超界）。"""
    import threading

    u = UnifiedNamespace(maxlen=50)
    threads = [
        threading.Thread(target=lambda: [u.publish_human("wecom://x", {"i": i}) for i in range(100)])
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(u.recent(n=10000)) == 50


def test_async_concurrent_publish_p1():
    """asyncio 多协程并发 publish（模拟 FastAPI 并发请求）：计数精确。"""
    import asyncio

    u = UnifiedNamespace(maxlen=100000)

    async def producer(pid: int):
        for i in range(100):
            u.publish_meeting(f"meet://p{pid}", {"topic": f"t-{pid}-{i}"})
            if i % 25 == 0:
                await asyncio.sleep(0)

    async def main():
        await asyncio.gather(*(producer(p) for p in range(10)))

    asyncio.run(main())
    assert u.channel_counts()[CHANNEL_MEETING] == 1000
