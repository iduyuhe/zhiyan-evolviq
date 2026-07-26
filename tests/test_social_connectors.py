"""社交通道接入测试（v29.9）

重点覆盖 Good First Issue「单测覆盖 token 拒绝」：
- 企微 SHA1 签名校验：正确通过 / 错误拒绝
- 钉钉 HmacSHA256 加签校验：正确通过 / 错误拒绝
- 回调端点：错误签名 → 403
- 启用态 happy path：签名正确 → 解析 → 入 UNS social 路
- 配置 UI 连通性：/connectivity 聚合 + /connectivity/gateway 单协议测试

注：runtime 路由实际挂载在 /connectors、/connectivity（无 /api 前缀；
/api 前缀由 nginx 反代剥离后转发）。本测试直打 runtime，故路径不含 /api。
"""

import asyncio
import os

import pytest


def _set_settings(**kw):
    from src.common.config import settings
    prev = {k: getattr(settings, k) for k in kw}
    for k, v in kw.items():
        setattr(settings, k, v)
    return prev


# ============ 1. 签名校验单测（token 拒绝核心）============

def test_wecom_signature_verify_accept_and_reject():
    from src.runtime.connectors.wecom_ingest import verify_wecom_signature

    token, ts, nonce = "mytoken", "1600000000", "abc123"
    arr = sorted([token, ts, nonce])
    import hashlib
    sig = hashlib.sha1("".join(arr).encode()).hexdigest()

    assert verify_wecom_signature(token, ts, nonce, sig) is True
    assert verify_wecom_signature(token, ts, nonce, "deadbeef") is False
    assert verify_wecom_signature(token, ts, nonce, "") is False


def test_dingtalk_sign_verify_accept_and_reject():
    from src.runtime.connectors.dingtalk_ingest import verify_dingtalk_sign
    import base64, hashlib, hmac

    secret, ts = "SECxxxx", "1600000000"
    s = base64.b64encode(
        hmac.new(secret.encode(), f"{ts}\n{secret}".encode(), hashlib.sha256).digest()
    ).decode()

    assert verify_dingtalk_sign(secret, ts, s) is True
    assert verify_dingtalk_sign(secret, ts, "wrongsign") is False
    assert verify_dingtalk_sign(secret, ts, "") is False


# ============ 2. 启用态 happy path：签名正确 → UNS social ============

def test_wecom_enabled_happy_path_publishes_to_uns():
    from src.runtime.connectors.wecom_ingest import WeComConnector
    from src.runtime.uns import uns, CHANNEL_SOCIAL
    import hashlib, json

    prev = _set_settings(wecom_token="tok")
    try:
        c = WeComConnector()
        assert c.enabled is True

        ts, nonce = "1700000000", "n1"
        arr = sorted([c.token, ts, nonce])
        sig = hashlib.sha1("".join(arr).encode()).hexdigest()
        body = json.dumps({"content": "产线3 设备异常", "from": "zhang", "type": "text"}).encode()

        parsed = c.verify_message(sig, ts, nonce, body)
        assert parsed is not None
        assert "产线3" in parsed["content"]

        before = uns.channel_counts().get(CHANNEL_SOCIAL, 0)
        evt_id = c.publish(text=parsed["content"], entities=[f"wecom:{parsed['from_user']}"])
        after = uns.channel_counts().get(CHANNEL_SOCIAL, 0)
        assert evt_id is not None
        assert after == before + 1
    finally:
        _set_settings(**prev)


def test_dingtalk_enabled_happy_path():
    from src.runtime.connectors.dingtalk_ingest import DingTalkConnector, verify_dingtalk_sign
    import base64, hashlib, hmac, json

    prev = _set_settings(dingtalk_secret="SECtest")
    try:
        c = DingTalkConnector()
        assert c.enabled is True
        ts = "1700000000"
        s = base64.b64encode(
            hmac.new(c.secret.encode(), f"{ts}\n{c.secret}".encode(), hashlib.sha256).digest()
        ).decode()
        body = json.dumps({"text": {"content": "会议改到周四"}, "msgtype": "text"}).encode()
        parsed = c.verify_and_parse(ts, s, body)
        assert parsed is not None
        assert "周四" in parsed["content"]
    finally:
        _set_settings(**prev)


# ============ 3. 端点级拒绝（错误签名 → 403）============

@pytest.fixture
def client():
    from fastapi import FastAPI, Depends
    from src.runtime.api.connectors import callback_router, admin_router
    from src.runtime.api.connectivity import router as conn_router
    from src.runtime.authn.deps import require_auth
    from httpx import ASGITransport, AsyncClient

    app = FastAPI()
    app.include_router(callback_router)
    app.include_router(admin_router, dependencies=[Depends(require_auth)])
    app.include_router(conn_router, dependencies=[Depends(require_auth)])
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_wecom_callback_rejects_bad_signature(client):
    r = await client.get(
        "/connectors/wecom/callback",
        params={"msg_signature": "bad", "timestamp": "1", "nonce": "n", "echostr": "e"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_dingtalk_callback_rejects_bad_sign(client):
    r = await client.post(
        "/connectors/dingtalk/callback",
        params={"timestamp": "1", "sign": "bad"},
        content=b'{"text":{"content":"x"}}',
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_connectors_list_ok(client):
    r = await client.get("/connectors")
    assert r.status_code == 200
    data = r.json()
    assert "connectors" in data
    kinds = {c["name"] for c in data["connectors"]}
    assert {"wecom", "dingtalk", "email"}.issubset(kinds)


@pytest.mark.asyncio
async def test_connectivity_overview_ok(client):
    r = await client.get("/connectivity")
    assert r.status_code == 200
    data = r.json()
    assert "db" in data and "gateways" in data and "data_sources" in data


@pytest.mark.asyncio
async def test_gateway_connectivity_test(client):
    r = await client.post(
        "/connectivity/gateway",
        json={"protocol": "opcua", "endpoint": "opc.tcp://127.0.0.1:1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["protocol"] == "opcua"
    assert "ok" in data and "latency_ms" in data
