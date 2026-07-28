"""监控告警测试（v28.3：回写积压 / 网关断流 / 登录异常）"""

import time

import pytest

from src.runtime.monitoring import AlertMonitor, alert_monitor
from src.runtime.uns import uns


@pytest.fixture(autouse=True)
def _isolate():
    from src.runtime.data_sources.writeback import writeback_bridge

    alert_monitor.clear()
    wb_pending_before = list(writeback_bridge._pending)
    yield
    alert_monitor.clear()
    # 恢复回写桥 pending 队列，避免污染 test_writeback 等其他用例
    writeback_bridge._pending = wb_pending_before


# ---------------- ① 回写积压 ----------------

@pytest.mark.asyncio
async def test_writeback_backlog_alert(monkeypatch):
    from src.runtime.data_sources.writeback import writeback_bridge
    from src.runtime.data_sources.registry import registry
    from src.runtime.data_sources.base import DataSourceKind

    monkeypatch.setenv("ZHIYAN_ALERT_WB_PENDING", "3")
    registry.unregister(DataSourceKind.MES)  # 确保连接器不可用 → 全部进 pending
    before = len(writeback_bridge.pending())
    need = max(0, 3 - before)
    for i in range(need):
        await writeback_bridge.submit(system="mes", agent="a", decision_type="t", payload={"i": i})
    a = alert_monitor.check_writeback_backlog()
    assert a is not None
    assert a.kind == "writeback_backlog"
    assert a.detail["pending"] >= 3
    # cooldown 去重：第二次不重复发布
    assert alert_monitor.check_writeback_backlog() is None


def test_writeback_backlog_below_threshold(monkeypatch):
    monkeypatch.setenv("ZHIYAN_ALERT_WB_PENDING", "999999")
    assert alert_monitor.check_writeback_backlog() is None


# ---------------- ② 网关断流 ----------------

def test_gateway_stale_alert(monkeypatch):
    from src.runtime.data_sources.registry import registry
    from src.runtime.data_sources.connectors.energy_twin import EnergyTwinDataSource

    monkeypatch.setenv("ZHIYAN_ALERT_TWIN_STALE_S", "60")
    twin = EnergyTwinDataSource(tenant_id="default")
    twin.ingest({"power_kw__L1": 42.0}, source="test")
    twin.twin_state["updated_at"] = time.time() - 3600  # 人为造 1h 断流
    registry.register(twin)
    fired = alert_monitor.check_gateway_stale("default")
    assert any(a.kind == "gateway_stale" for a in fired)
    # 从未流入的孪生体（updated_at=None）不算断流
    fresh = EnergyTwinDataSource(tenant_id="default")
    assert fresh.twin_state["updated_at"] is None


def test_gateway_fresh_no_alert(monkeypatch):
    from src.runtime.data_sources.registry import registry
    from src.runtime.data_sources.connectors.energy_twin import EnergyTwinDataSource

    monkeypatch.setenv("ZHIYAN_ALERT_TWIN_STALE_S", "600")
    twin = EnergyTwinDataSource(tenant_id="default")
    twin.ingest({"power_kw__L1": 42.0}, source="test")  # 刚更新
    registry.register(twin)
    fired = alert_monitor.check_gateway_stale("default")
    assert not any(a.detail.get("source") == twin.name and a.kind == "gateway_stale" for a in fired)


# ---------------- ③ 登录异常 ----------------

def test_login_anomaly_threshold(monkeypatch):
    monkeypatch.setenv("ZHIYAN_ALERT_LOGIN_FAILS", "3")
    m = AlertMonitor()
    assert m.record_login_failure("admin", ip="1.2.3.4") is None
    assert m.record_login_failure("admin") is None
    a = m.record_login_failure("admin")
    assert a is not None and a.kind == "login_anomaly"
    assert a.detail["failures"] == 3


def test_login_success_resets_window(monkeypatch):
    monkeypatch.setenv("ZHIYAN_ALERT_LOGIN_FAILS", "3")
    m = AlertMonitor()
    m.record_login_failure("bob")
    m.record_login_failure("bob")
    m.record_login_success("bob")  # 清空窗口
    assert m.record_login_failure("bob") is None  # 重新计数


def test_login_window_expiry(monkeypatch):
    monkeypatch.setenv("ZHIYAN_ALERT_LOGIN_FAILS", "2")
    monkeypatch.setenv("ZHIYAN_ALERT_LOGIN_WINDOW_S", "1")
    m = AlertMonitor()
    m._login_fails["eve"] = [time.time() - 10]  # 窗口外旧失败
    assert m.record_login_failure("eve") is None  # 旧记录被滑出，只算 1 次


# ---------------- 告警进 UNS system 路 ----------------

def test_alert_published_to_uns(monkeypatch):
    monkeypatch.setenv("ZHIYAN_ALERT_LOGIN_FAILS", "1")
    m = AlertMonitor()
    n_before = len(uns.query(channel="system"))
    a = m.record_login_failure("mallory")
    assert a is not None
    evs = uns.query(channel="system")
    assert len(evs) == n_before + 1
    assert evs[-1]["type"] == "alert"
    assert evs[-1]["payload"]["kind"] == "login_anomaly"


# ---------------- ④ 网关 simulated 降级显性告警（P1②） ----------------

def test_gateway_degraded_alert_p1():
    """P1②：simulated 降级必须显性告警（UNS system 路 + 本地缓冲），并 cooldown 去重。"""
    a = alert_monitor.report_gateway_degraded("modbus", tenant_id="default", phase="startup")
    assert a is not None
    assert a.kind == "gateway_degraded"
    assert a.severity == "warning"
    assert a.detail["mode"] == "simulated"
    # UNS system 路可查
    evs = [e for e in uns.query(channel="system", n=20)
           if e.get("payload", {}).get("kind") == "gateway_degraded"]
    assert len(evs) >= 1
    # cooldown 去重
    assert alert_monitor.report_gateway_degraded("modbus", phase="startup") is None
    # persistent 阶段为 critical（不同 phase 共用 key，先清再发）
    alert_monitor.clear()
    p = alert_monitor.report_gateway_degraded("mqtt", phase="persistent")
    assert p is not None and p.severity == "critical"


def test_gateway_recovered_alert_p1():
    """P1②：simulated→真实连接升级发恢复通知（info 级）。"""
    a = alert_monitor.report_gateway_recovered("opcua", mode="opcua-live")
    assert a is not None
    assert a.kind == "gateway_recovered"
    assert a.severity == "info"
    assert a.detail["mode"] == "opcua-live"


@pytest.mark.asyncio
async def test_gateway_manager_fires_degraded_on_init_p1():
    """P1②：GatewayManager.initialize() 首连回退 simulated 时实际触发告警。"""
    from src.gateways.manager import GatewayManager

    alert_monitor.clear()
    mgr = GatewayManager()  # 测试环境无真实 PLC/Broker → 必然全回退 simulated
    await mgr.initialize()
    degraded = alert_monitor.alerts(kind="gateway_degraded")
    assert len(degraded) >= 1
    names = {d["detail"]["gateway"] for d in degraded}
    assert names & {"modbus", "mqtt", "opcua", "ipc_cfx"}


@pytest.mark.asyncio
async def test_twin_feed_carries_source_mode_p1():
    """P1②：网关上行 UNS 事件带 _source_mode 溯源标记，且不污染孪生数值。"""
    from src.gateways.manager import GatewayManager

    mgr = GatewayManager()
    await mgr.initialize()
    dps = await mgr.read("modbus", "line_1_temp")
    assert dps
    evs = uns.query(channel="gateway", n=5)
    tagged = [e for e in evs if e.get("payload", {}).get("_source_mode")]
    assert tagged, "网关事件必须带 _source_mode 标记"
    assert tagged[-1]["payload"]["_source_mode"] == "simulated"


# ---------------- API 端点 ----------------

@pytest.mark.asyncio
async def test_monitoring_api(monkeypatch):
    import httpx
    from src.runtime.main import app

    monkeypatch.setenv("ZHIYAN_ALERT_LOGIN_FAILS", "1")
    alert_monitor.record_login_failure("api-test-user")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/monitoring/alerts", params={"kind": "login_anomaly"})
        assert r.status_code == 200
        assert any(a["detail"]["username"] == "api-test-user" for a in r.json()["alerts"])
        s = await c.get("/monitoring/status")
        assert s.status_code == 200
        assert "thresholds" in s.json()
        chk = await c.post("/monitoring/check")
        assert chk.status_code == 200
        assert "fired" in chk.json()


# ---------------- 登录失败挂钩 authn ----------------

@pytest.mark.asyncio
async def test_login_failure_hook(monkeypatch):
    import httpx
    from src.runtime.main import app

    monkeypatch.setenv("ZHIYAN_ALERT_LOGIN_FAILS", "2")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        for _ in range(2):
            r = await c.post("/authn/login", json={"username": "no-such-user", "password": "wrong"})
            assert r.status_code == 401
    alerts = alert_monitor.alerts(kind="login_anomaly")
    assert any(a["detail"]["username"] == "no-such-user" for a in alerts)
