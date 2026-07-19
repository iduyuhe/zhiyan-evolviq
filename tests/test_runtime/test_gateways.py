"""工业协议网关闭环测试（V1-3）

经真实 HTTP 应用验证四类网关（Modbus/MQTT/OPC-UA/IPC-CFX）的健康总览、单网关详情与读数；
沙箱无真实 Server/Broker，网关自动回退模拟模式，关注逻辑而非外部依赖。
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_gateways_overview(client):
    """全部网关健康总览：4 类网关就绪，模拟模式。"""
    resp = await client.get("/gateways")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["ready"] == 4
    assert "simulated" in data["modes"]
    for name in ("modbus", "mqtt", "opcua", "ipc_cfx"):
        assert name in data["gateways"], f"缺少网关 {name}"


@pytest.mark.asyncio
async def test_gateway_detail_opcua(client):
    """OPC-UA 单网关详情。"""
    resp = await client.get("/gateways/opcua")
    assert resp.status_code == 200
    h = resp.json()
    assert h["mode"] in ("simulated", "opcua")
    assert h["endpoint"] == "opc.tcp://localhost:4840"


@pytest.mark.asyncio
async def test_gateway_unknown_404(client):
    """未知网关应 404。"""
    resp = await client.get("/gateways/nope")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_read_opcua_nodes(client):
    """OPC-UA 读全部节点返回数据点。"""
    resp = await client.post("/gateways/opcua/read", json={"address": "*", "count": 8})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] > 0
    assert len(body["points"]) <= 8
    assert body["points"][0]["tag"].startswith("ns=2;s=")


@pytest.mark.asyncio
async def test_read_modbus_register(client):
    """Modbus 读指定寄存器。"""
    resp = await client.post("/gateways/modbus/read", json={"address": "line_1_status", "count": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert "line_1_status" in body["points"][0]["tag"]


@pytest.mark.asyncio
async def test_read_ipc_cfx_events(client):
    """IPC-CFX 读事件主题返回数据点。"""
    resp = await client.post("/gateways/ipc_cfx/read", json={"address": "*", "count": 4})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] > 0
    assert body["points"][0]["tag"].startswith("CFX.")
