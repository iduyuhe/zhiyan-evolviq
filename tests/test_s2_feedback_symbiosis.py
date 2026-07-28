"""S2-6 #313：杜特第0号用户开通 + 共生进化环反馈入口 专项测试

覆盖：
- 脱敏管道（剥离租户名/邮箱/手机/证件/卡号）
- 反馈提交 + 租户隔离
- 脱敏审核门 → GitHub Issue（from-customer，mock）
- 48h 首响应 SLA 看板
- API 权限（viewer 不可审核 / 跨租户不可操作 / 管理员可见看板）
- 杜特第0号租户 + 团队账号开通（seed_dute_tenant 幂等）
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.authn.service import authn_service
from src.runtime.feedback_store import desensitize, feedback_store
from src.runtime.github_client import create_issue
from src.runtime.seed_dute import DUTE_TENANT_ID, seed_dute_tenant
from src.runtime.tenant_store import tenant_store

pytestmark = pytest.mark.asyncio

TENANT_A = "fb-t-a"
TENANT_B = "fb-t-b"
TEST_ADMIN_PW = "TestAdmin123!"


def _client():
    from src.runtime.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _admin_token() -> str:
    await authn_service.ensure_admin(password=TEST_ADMIN_PW)
    from src.runtime.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})
        return r.json()["access_token"]


async def _tenant_admin_token(username: str, tenant_id: str) -> str:
    await authn_service.create_user(
        username=username, password="TaPw123!", role="tenant_admin", tenant_id=tenant_id
    )
    from src.runtime.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/authn/login", json={"username": username, "password": "TaPw123!"})
        return r.json()["access_token"]


# ---------- 脱敏管道 ----------

class TestDesensitize:
    async def test_strips_tenant_name_and_email(self):
        out = desensitize("上海杜特企业管理咨询有限公司 联系 duyuhe@dute.com", "上海杜特企业管理咨询有限公司")
        assert "上海杜特企业管理咨询有限公司" not in out
        assert "duyuhe@dute.com" not in out
        assert "〔租户〕" in out
        assert "〔邮箱〕" in out

    async def test_strips_phone_and_bank(self):
        out = desensitize("手机13800138000 卡号6222021234567890123")
        assert "13800138000" not in out
        assert "6222021234567890123" not in out
        assert "〔手机〕" in out and "〔卡号〕" in out

    async def test_empty_returns_empty(self):
        assert desensitize(None) == ""
        assert desensitize("") == ""

    async def test_idcard_redacted(self):
        out = desensitize("身份证 11010119900307123X")
        assert "11010119900307123X" not in out
        assert "〔证件号〕" in out


# ---------- 提交 + 租户隔离 ----------

class TestStoreSubmit:
    @pytest.mark.asyncio
    async def test_submit_and_isolation(self):
        rec = await feedback_store.submit(TENANT_A, "u1", "idea", None, None, "建议增加替代料推荐")
        try:
            assert rec["tenant_id"] == TENANT_A
            assert rec["status"] == "received"
            assert rec["first_response_due_at"] is not None  # 48h SLA 已算
            assert len(feedback_store.list_for(TENANT_A)) == 1
            assert feedback_store.list_for(TENANT_B) == []
        finally:
            await feedback_store.delete(rec["id"])

    @pytest.mark.asyncio
    async def test_invalid_type_rejected(self):
        with pytest.raises(ValueError):
            await feedback_store.submit(TENANT_A, "u1", "bogus", None, None, "x")


# ---------- 脱敏审核门 → GitHub Issue ----------

class TestEscalate:
    @pytest.mark.asyncio
    async def test_escalate_creates_issue(self, monkeypatch):
        monkeypatch.setattr(
            "src.runtime.feedback_store.create_issue",
            lambda title, body, labels=None: {"url": "https://github.com/x/1", "number": 1},
        )
        rec = await feedback_store.submit(TENANT_A, "u1", "idea", None, None, "上海杜特建议增加替代料推荐")
        try:
            res = await feedback_store.escalate(rec["id"], reviewer="op", tenant_name="上海杜特企业管理咨询有限公司")
            assert res["success"] is True
            assert res["status"] == "issued"
            assert res["github_issue_url"] == "https://github.com/x/1"
            # 提报内容已脱敏（租户名不出现在 desensitized_text）
            assert "上海杜特" not in (res["desensitized_text"] or "")
            # responded_at 已写入（48h SLA 达成）
            assert feedback_store.get(rec["id"])["responded_at"] is not None
        finally:
            await feedback_store.delete(rec["id"])

    @pytest.mark.asyncio
    async def test_like_without_text_not_escalatable(self):
        rec = await feedback_store.submit(TENANT_A, "u1", "like", None, None, None)
        try:
            with pytest.raises(ValueError):
                await feedback_store.escalate(rec["id"], reviewer="op", tenant_name="")
        finally:
            await feedback_store.delete(rec["id"])


# ---------- 48h SLA 看板 ----------

class TestBoard:
    @pytest.mark.asyncio
    async def test_board_stats(self):
        r1 = await feedback_store.submit(TENANT_A, "u1", "idea", None, None, "想法一")
        r2 = await feedback_store.submit(TENANT_A, "u2", "dislike", None, None, "不准")
        try:
            b = feedback_store.board_stats(TENANT_A)
            assert b["total"] == 2
            assert b["pending"] == 2
            assert b["overdue"] == 0  # 刚提交未逾期
            assert b["sla_rate"] is None  # 无闭环项
            # 跨租户隔离
            assert feedback_store.board_stats(TENANT_B)["total"] == 0
        finally:
            await feedback_store.delete(r1["id"])
            await feedback_store.delete(r2["id"])


# ---------- API 权限 ----------

class TestFeedbackAPI:
    @pytest.mark.asyncio
    async def test_submit_and_tenant_isolation(self):
        async with _client() as c:
            r = await c.post("/feedback", json={"feedback_type": "idea", "text": "想法"},
                             headers={"X-Tenant-Key": TENANT_A})
            assert r.status_code == 200
            fb_id = r.json()["feedback"]["id"]
            # 同租户可见
            r = await c.get("/feedback", headers={"X-Tenant-Key": TENANT_A})
            assert r.json()["total"] == 1
            # 跨租户不可见
            r = await c.get("/feedback", headers={"X-Tenant-Key": TENANT_B})
            assert r.json()["total"] == 0
            await feedback_store.delete(fb_id)

    @pytest.mark.asyncio
    async def test_board_forbidden_for_viewer(self):
        async with _client() as c:
            r = await c.get("/feedback/board", headers={"X-Tenant-Key": TENANT_A})
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_escalate_requires_admin(self):
        async with _client() as c:
            r = await c.post("/feedback", json={"feedback_type": "idea", "text": "想法"},
                             headers={"X-Tenant-Key": TENANT_A})
            fb_id = r.json()["feedback"]["id"]
            # viewer（X-Tenant-Key）提报 → 403
            r = await c.post(f"/feedback/{fb_id}/escalate", headers={"X-Tenant-Key": TENANT_A})
            assert r.status_code == 403
            await feedback_store.delete(fb_id)

    @pytest.mark.asyncio
    async def test_superadmin_escalate_success(self, monkeypatch):
        monkeypatch.setattr(
            "src.runtime.feedback_store.create_issue",
            lambda title, body, labels=None: {"url": "https://github.com/x/9", "number": 9},
        )
        async with _client() as c:
            r = await c.post("/feedback", json={"feedback_type": "idea", "text": "想法"},
                             headers={"X-Tenant-Key": TENANT_A})
            fb_id = r.json()["feedback"]["id"]
            tok = await _admin_token()
            r = await c.post(f"/feedback/{fb_id}/escalate", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code == 200
            assert r.json()["success"] is True
            assert r.json()["github_issue_number"] == 9
            await feedback_store.delete(fb_id)

    @pytest.mark.asyncio
    async def test_cross_tenant_escalate_forbidden(self):
        """租户管理员只能审核本租户反馈，不能操作他租户。"""
        async with _client() as c:
            r = await c.post("/feedback", json={"feedback_type": "idea", "text": "想法"},
                             headers={"X-Tenant-Key": TENANT_A})
            fb_id = r.json()["feedback"]["id"]
            # 为 TENANT_B 建一个租户管理员
            tok_b = await _tenant_admin_token("tb_admin", TENANT_B)
            r = await c.post(f"/feedback/{fb_id}/escalate", headers={"Authorization": f"Bearer {tok_b}"})
            assert r.status_code == 403
            await feedback_store.delete(fb_id)


# ---------- 杜特第0号用户开通 ----------

class TestDuteSeed:
    @pytest.mark.asyncio
    async def test_dute_tenant_and_team_provisioned(self):
        summary = await seed_dute_tenant()
        assert tenant_store.get(DUTE_TENANT_ID) is not None
        users = await authn_service.list_users(DUTE_TENANT_ID)
        usernames = {u["username"] for u in users}
        assert {"dute_admin", "duyuhe", "dute_team"}.issubset(usernames)
        # 幂等：再次调用不报错、不重复建号
        summary2 = await seed_dute_tenant()
        assert summary2["created"] is False

    @pytest.mark.asyncio
    async def test_dute_team_can_login(self):
        await seed_dute_tenant()
        async with _client() as c:
            r = await c.post("/authn/login", json={"username": "duyuhe", "password": "Dute@duyuhe2026"})
            assert r.status_code == 200
            assert r.json()["user"]["tenant_id"] == DUTE_TENANT_ID
