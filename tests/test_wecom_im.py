"""IM 对接集成测试（扫码即联 + 移动端审核/查询，2026-08-03）

覆盖：
1. 零真名脱敏（src/common/leak）：contains_leak / sanitize_leak
2. 扫码即联绑定（binding）：生成/确认/解析/过期/is_bound
3. 审批卡片（service）：build_approval_card / build_result_card 结构 + send_template_card payload
4. 入站事件解析（wecom_ingest）：parse_approval_event_key + _parse_wecom_xml event 字段
5. IM 桥接（im_bridge）：process_approval 通过/驳回 + 租户 fail-closed；handle_text_query 只读
6. 回调接线（connectors）：企微回调把审批按钮路由到 im_bridge.handle_inbound
"""

import importlib

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.common.leak import contains_leak, sanitize_leak
from src.runtime.wecom.binding import binding_store, BindSession
from src.runtime.wecom.service import WeComService


@pytest.fixture
def wecom_config(monkeypatch):
    """注入测试凭证（非真实密钥，仅测试用）。"""
    monkeypatch.setattr("src.common.config.settings.wecom_corpid", "ww_test_corpid")
    monkeypatch.setattr("src.common.config.settings.wecom_secret", "test-secret")
    monkeypatch.setattr("src.common.config.settings.wecom_agentid", "1000002")
    return None



# ============ 1. 零真名脱敏 ============

class TestLeak:
    def test_contains_leak(self):
        assert contains_leak("中兴缺料预警") == ["中兴"]
        assert contains_leak("与台积电对标") == ["台积电"]
        assert contains_leak("普通文本无泄漏") == []

    def test_sanitize_leak_long_before_short(self):
        # 长 token 优先："长电科技" 不应残留为 "长电＊＊"
        out = sanitize_leak("长电科技产线")
        assert "长电科技" not in out
        assert "长电" not in out
        assert "＊" in out

    def test_sanitize_case_insensitive_tokens(self):
        out = sanitize_leak("ZTE 与 zte 都封")
        assert "ZTE" not in out and "zte" not in out


# ============ 2. 扫码即联绑定 ============

class TestBinding:
    def test_create_and_resolve(self):
        store = binding_store  # 直接用单例（测试隔离靠不同 tenant）
        s = store.create_bind_session("tenantA")
        assert s.token and not s.confirmed
        payload = store.build_qr_payload(s.token)
        assert payload["token"] == s.token
        assert "zhiyan.weomnitech.com.cn/wecom/bind/confirm" in payload["confirm_url"]

    def test_confirm_and_resolve_tenant_by_corp(self):
        store = binding_store
        s = store.create_bind_session("tenantB")
        r = store.confirm_bind(s.token, "corpB", "userB")
        assert r["ok"] is True
        assert store.resolve_tenant_by_corp("corpB") == "tenantB"
        assert store.resolve_tenant_by_user("userB") == "tenantB"
        assert store.resolve_approver_userid("tenantB") == "userB"
        assert store.is_bound("tenantB") is True

    def test_confirm_unknown_token(self):
        assert binding_store.confirm_bind("nope", "c", "u")["reason"] == "token_not_found"

    def test_confirm_expired(self):
        s = binding_store.create_bind_session("tenantC")
        s.created_at = s.created_at - 9999  # 人为过期
        r = binding_store.confirm_bind(s.token, "corpC", "userC")
        assert r["ok"] is False
        assert r["reason"] == "token_expired"

    def test_tenant_mismatch_fail_closed(self):
        # 未绑定 corp → 解析 None（绝不回落 default）
        assert binding_store.resolve_tenant_by_corp("never_bound_corp") is None


# ============ 3. 审批卡片 ============

class TestApprovalCard:
    def test_build_approval_card_structure(self):
        s = WeComService()
        card = s.build_approval_card("sess1", "28nm 产线缺料", "摘要", "tenantX")
        assert card["msgtype"] == "template_card"
        tc = card["template_card"]
        assert tc["card_type"] == "button_interaction"
        keys = [b["key"] for b in tc["button_list"]]
        assert "APPROVE:sess1" in keys
        assert "REJECT:sess1" in keys

    def test_build_result_card_structure(self):
        s = WeComService()
        card = s.build_result_card("执行结果", "内容")
        assert card["template_card"]["card_type"] == "text_notice"

    @pytest.mark.asyncio
    async def test_send_template_card_payload(self, wecom_config, monkeypatch):
        import httpx

        s = WeComService()
        captured = {}

        async def fake_post(url, params=None, json=None, timeout=None):
            if url.endswith("gettoken"):
                return _FakeResp({"errcode": 0, "access_token": "tok", "expires_in": 7200})
            captured["body"] = json
            return _FakeResp({"errcode": 0, "msgid": "M1"})

        async def fake_get(url, params=None, timeout=None):
            return _FakeResp({"errcode": 0, "access_token": "tok", "expires_in": 7200})

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(fake_get, fake_post))
        card = s.build_approval_card("sess9", "标题", "摘要", "tenantY")
        r = await s.send_template_card(["uA"], card)
        assert r["ok"] is True
        assert captured["body"]["touser"] == "uA"
        assert captured["body"]["msgtype"] == "template_card"
        assert captured["body"]["template_card"]["task_id"] == "sess9"


# ============ 4. 入站事件解析 ============

class TestIngestEvent:
    def test_parse_approval_event_key(self):
        from src.runtime.connectors.wecom_ingest import parse_approval_event_key

        assert parse_approval_event_key("APPROVE:sess1") == {"action": "approve", "session_id": "sess1"}
        assert parse_approval_event_key("REJECT:sess2") == {"action": "reject", "session_id": "sess2"}
        assert parse_approval_event_key("JUNK:x") is None
        assert parse_approval_event_key(None) is None

    def test_parse_xml_event_fields(self):
        from src.runtime.connectors.wecom_ingest import _parse_wecom_xml

        xml = (
            "<xml><FromUserName><![CDATA[u1]]></FromUserName>"
            "<MsgType><![CDATA[event]]></MsgType>"
            "<Event><![CDATA[template_card_event]]></Event>"
            "<EventKey><![CDATA[APPROVE:sess7]]></EventKey>"
            "<TaskId><![CDATA[sess7]]></TaskId></xml>"
        )
        d = _parse_wecom_xml(xml)
        assert d["from_user"] == "u1"
        assert d["msg_type"] == "event"
        assert d["event"] == "template_card_event"
        assert d["event_key"] == "APPROVE:sess7"
        assert d["task_id"] == "sess7"


# ============ 5. IM 桥接 ============

class _FakeEngine:
    def __init__(self, session=None, tenant="tenant1"):
        self._session = session or {"tenant_id": tenant, "goal": "g", "agent": "supply_chain", "status": "awaiting_approval"}
        self.executed = None
        self.rejected = None

    def get_session(self, sid):
        return self._session

    async def execute(self, sid, tenant_id=None):
        self.executed = (sid, tenant_id)
        return {"summary": "执行完成：已批准缺料预案"}

    async def reject(self, sid, feedback=None, tenant_id=None):
        self.rejected = (sid, tenant_id)
        return {"status": "rejected", "feedback": feedback}

    async def plan(self, sid, goal, tenant_id=None, auth_boundary_id=None):
        return f"规划摘要：分析 {goal}"


@pytest.mark.asyncio
async def test_process_approval_approve(monkeypatch):
    from src.runtime.wecom import im_bridge

    eng = _FakeEngine(session={"tenant_id": "tenant1", "agent": "supply_chain"}, tenant="tenant1")
    monkeypatch.setattr("src.runtime.api.sessions.get_engine", lambda: eng)
    r = await im_bridge.process_approval("sess1", "approve", "user1", "tenant1")
    assert r["ok"] is True
    assert r["action"] == "approve"
    assert eng.executed == ("sess1", "tenant1")


@pytest.mark.asyncio
async def test_process_approval_reject(monkeypatch):
    from src.runtime.wecom import im_bridge

    eng = _FakeEngine(session={"tenant_id": "tenant1"}, tenant="tenant1")
    monkeypatch.setattr("src.runtime.api.sessions.get_engine", lambda: eng)
    r = await im_bridge.process_approval("sess2", "reject", "user1", "tenant1")
    assert r["ok"] is True
    assert eng.rejected == ("sess2", "tenant1")


@pytest.mark.asyncio
async def test_process_approval_tenant_mismatch_fail_closed(monkeypatch):
    from src.runtime.wecom import im_bridge

    # session 属 tenant1，但入站解析出 tenant2（跨租户）→ 拒绝
    eng = _FakeEngine(session={"tenant_id": "tenant1"}, tenant="tenant1")
    monkeypatch.setattr("src.runtime.api.sessions.get_engine", lambda: eng)
    r = await im_bridge.process_approval("sess3", "approve", "userX", "tenant2")
    assert r["ok"] is False
    assert r["reason"] == "tenant_mismatch"
    assert eng.executed is None  # 绝不执行


@pytest.mark.asyncio
async def test_handle_text_query_read_only(monkeypatch):
    from src.runtime.wecom import im_bridge

    eng = _FakeEngine(session={"tenant_id": "tenant1", "agent": "supply_chain"}, tenant="tenant1")
    monkeypatch.setattr("src.runtime.api.sessions.get_engine", lambda: eng)
    r = await im_bridge.handle_text_query("我司缺料风险如何？", "user1", "tenant1")
    assert r["ok"] is True
    assert r["read_only"] is True
    assert r["routed_agent"] == "supply_chain"
    assert eng.executed is None  # 只读：绝不 execute


@pytest.mark.asyncio
async def test_sanitize_inbound_text(monkeypatch):
    from src.runtime.wecom import im_bridge

    eng = _FakeEngine(session={"tenant_id": "tenant1", "agent": "supply_chain"}, tenant="tenant1")
    monkeypatch.setattr("src.runtime.api.sessions.get_engine", lambda: eng)
    r = await im_bridge.handle_text_query("与中兴对标分析", "user1", "tenant1")
    # 出站预览应脱敏真名
    assert "中兴" not in str(r)


# ============ 6. 回调接线 ============

@pytest.mark.asyncio
async def test_wecom_callback_routes_approval_to_bridge(monkeypatch):
    from src.runtime.api import connectors as connectors_api

    captured = {}

    async def fake_handle(parsed, corp_id=None):
        captured["parsed"] = parsed
        captured["corp_id"] = corp_id
        return {"ok": True, "action": "approve"}

    monkeypatch.setattr("src.runtime.wecom.im_bridge.handle_inbound", fake_handle)

    class FakeConn:
        enabled = True
        corp_id = "corpRoute"

        def verify_message(self, *a, **k):
            return {
                "content": "",
                "from_user": "userRoute",
                "msg_type": "event",
                "event": "template_card_event",
                "event_key": "APPROVE:sessRoute",
                "task_id": "sessRoute",
            }

    class FakeManager:
        def get(self, name):
            return FakeConn()

    monkeypatch.setattr(connectors_api, "manager", FakeManager())

    app = FastAPI()
    app.include_router(connectors_api.callback_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/connectors/wecom/callback",
            params={"msg_signature": "x", "timestamp": "1", "nonce": "n"},
            content=b"{}",
        )
    assert r.status_code == 200
    assert r.json()["status"] == "im_routed"
    assert captured["parsed"]["event_key"] == "APPROVE:sessRoute"
    assert captured["corp_id"] == "corpRoute"


# ============ 测试辅助（与 test_wecom_service 同款 FakeClient）============

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
