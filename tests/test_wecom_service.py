"""企业微信自建应用适配测试（移动端第②阶骨架，2026-08-02）

覆盖：
1. 未配置 → status unconfigured / get_access_token None / sign None / send 降级（优雅降级铁律）
2. 配置后 access_token 带缓存（mock httpx）
3. agentConfig 签名确定性：同输入同输出，且 sha1 结构合法
4. send_app_message payload 结构（touser 拼接 / textcard）
5. API 层：/wecom/status 未配置时仍 200；/wecom/jsapi-signature 未配置 503；/wecom/push 未配置 503
"""

import hashlib

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.runtime.wecom.service import WeComService
from src.runtime.api.wecom import router as wecom_router


@pytest.fixture
def client():
    """独立 FastAPI 实例（带 wecom 路由），httpx ASGITransport 直打，无 lifespan。"""
    app = FastAPI()
    app.include_router(wecom_router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def no_wecom_config(monkeypatch):
    """清空企微配置（未配置态）。"""
    monkeypatch.setattr("src.common.config.settings.wecom_corpid", "")
    monkeypatch.setattr("src.common.config.settings.wecom_secret", "")
    monkeypatch.setattr("src.common.config.settings.wecom_agentid", "")
    return None


@pytest.fixture
def wecom_config(monkeypatch):
    """注入测试凭证（非真实密钥，仅测试用）。"""
    monkeypatch.setattr("src.common.config.settings.wecom_corpid", "ww_test_corpid")
    monkeypatch.setattr("src.common.config.settings.wecom_secret", "test-secret")
    monkeypatch.setattr("src.common.config.settings.wecom_agentid", "1000002")
    return None


class TestWeComService:
    def test_unconfigured_status(self, no_wecom_config):
        s = WeComService()
        st = s.status()
        assert st["configured"] is False
        assert st["mode"] == "unconfigured"
        # 🔴 凭证铁律：状态响应绝不泄露任何密钥/agentid 明文
        blob = str(st)
        assert "test-secret" not in blob

    @pytest.mark.asyncio
    async def test_unconfigured_graceful_degradation(self, no_wecom_config):
        s = WeComService()
        assert await s.get_access_token() is None
        assert await s.get_jsapi_ticket() is None
        assert await s.sign_agent_config("https://example.com/") is None
        r = await s.send_app_message(["user1"], "缺料预警测试")
        assert r["ok"] is False
        assert r["reason"] in ("unconfigured_or_empty", "unconfigured")

    @pytest.mark.asyncio
    async def test_access_token_cached(self, wecom_config, monkeypatch):
        """mock httpx gettoken：token 返回一次后缓存，二次调用不再请求。"""
        import httpx

        s = WeComService()
        calls = {"n": 0}

        class FakeResp:
            def json(self):
                calls["n"] += 1
                return {"errcode": 0, "access_token": "tok_123", "expires_in": 7200}

        async def fake_get(url, params=None, timeout=None):
            assert "corpid=ww_test_corpid" in str(params) or params["corpid"] == "ww_test_corpid"
            return FakeResp()

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(fake_get))
        t1 = await s.get_access_token()
        t2 = await s.get_access_token()
        assert t1 == "tok_123" and t2 == "tok_123"
        assert calls["n"] == 1  # 缓存命中，未二次请求

    @pytest.mark.asyncio
    async def test_sign_agent_config_deterministic(self, wecom_config, monkeypatch):
        """签名确定性 + sha1 结构合法（同 ticket/url 同签名）。"""
        import httpx

        s = WeComService()

        async def fake_get(url, params=None, timeout=None):
            if url.endswith("gettoken"):
                return _FakeResp({"errcode": 0, "access_token": "tok_abc", "expires_in": 7200})
            return _FakeResp({"errcode": 0, "ticket": "js_ticket_xyz", "expires_in": 7200})

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(fake_get))
        sig = await s.sign_agent_config("https://zhiyan.weomnitech.com.cn/studio")
        assert sig is not None
        assert sig["corpid"] == "ww_test_corpid"
        assert sig["agentId"] == "1000002"
        raw = (
            f"jsapi_ticket=js_ticket_xyz&noncestr={sig['nonceStr']}"
            f"&timestamp={sig['timestamp']}&url={sig['url']}"
        )
        assert sig["signature"] == hashlib.sha1(raw.encode("utf-8")).hexdigest()
        assert len(sig["signature"]) == 40  # sha1 hex

    @pytest.mark.asyncio
    async def test_send_app_message_payload(self, wecom_config, monkeypatch):
        """推送 payload：touser 竖线拼接 + textcard + agentid。"""
        import httpx

        s = WeComService()
        captured = {}

        async def fake_post(url, params=None, json=None, timeout=None):
            if url.endswith("gettoken"):
                return _FakeResp({"errcode": 0, "access_token": "tok_abc", "expires_in": 7200})
            captured["body"] = json
            return _FakeResp({"errcode": 0, "msgid": "MSG_1"})

        async def fake_get(url, params=None, timeout=None):
            return _FakeResp({"errcode": 0, "access_token": "tok_abc", "expires_in": 7200})

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(fake_get, fake_post))
        r = await s.send_app_message(["u1", "u2"], "28nm 产线硅片缺料预警", title="缺料预警")
        assert r["ok"] is True
        assert r["msgid"] == "MSG_1"
        assert captured["body"]["touser"] == "u1|u2"
        assert captured["body"]["agentid"] == 1000002
        assert captured["body"]["msgtype"] == "textcard"
        assert captured["body"]["textcard"]["title"] == "缺料预警"
        assert "缺料" in captured["body"]["textcard"]["description"]


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, get=None, post=None):
        self._get = get or (lambda *a, **k: _FakeResp({}))
        self._post = post or (lambda *a, **k: _FakeResp({}))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, timeout=None):
        return await self._get(url, params=params, timeout=timeout)

    async def post(self, url, params=None, json=None, timeout=None):
        return await self._post(url, params=params, json=json, timeout=timeout)


# ============ API 层 ============


class TestWeComAPI:
    @pytest.mark.asyncio
    async def test_status_unconfigured_still_200(self, client, no_wecom_config):
        r = await client.get("/wecom/status")
        assert r.status_code == 200
        assert r.json()["configured"] is False

    @pytest.mark.asyncio
    async def test_signature_unconfigured_503(self, client, no_wecom_config):
        r = await client.post("/wecom/jsapi-signature", json={"url": "https://x.com/"})
        assert r.status_code == 503

    @pytest.mark.asyncio
    async def test_push_unconfigured_503(self, client, no_wecom_config):
        r = await client.post("/wecom/push", json={"userids": ["u1"], "content": "测试"})
        assert r.status_code == 503
