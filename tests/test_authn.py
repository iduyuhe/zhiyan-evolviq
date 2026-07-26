"""企业认证（authn）测试——本地登录 / JWT / RBAC / 用户管理

用 httpx ASGITransport 直连 app（不触发 lifespan，认证走内存态）。
管理员在 fixture 中显式 seed，保证登录链路可用。
"""

import httpx
import pytest

from src.runtime.authn.security import decode_jwt, encode_jwt, hash_password, verify_password
from src.runtime.authn.service import authn_service

pytestmark = pytest.mark.asyncio

TEST_ADMIN_PW = "TestAdmin123!"


@pytest.fixture
async def client():
    await authn_service.ensure_admin(password=TEST_ADMIN_PW)
    from src.runtime.main import app

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_password_hash_roundtrip():
    h = hash_password("secret")
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)


async def test_jwt_roundtrip():
    tok = encode_jwt({"sub": "admin", "role": "SUPERADMIN", "tenant_id": "default"})
    p = decode_jwt(tok)
    assert p["sub"] == "admin"
    # 非法 token 应抛 ValueError（被 get_user_from_token 捕获为 None）
    import pytest as _pytest

    with _pytest.raises(ValueError):
        decode_jwt("x.y.z")


async def test_login_success(client):
    r = await client.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "SUPERADMIN"
    # JWT 可解析
    u = authn_service.get_user_from_token(body["access_token"])
    assert u["username"] == "admin"


async def test_login_wrong_password_401(client):
    r = await client.post("/authn/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


async def test_me_requires_token_401(client):
    assert (await client.get("/authn/me")).status_code == 401
    # 非法 token
    r = await client.get("/authn/me", headers=_auth_header("garbage"))
    assert r.status_code == 401


async def test_superadmin_can_create_and_list(client):
    tok = (await client.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})).json()["access_token"]
    h = _auth_header(tok)
    cu = await client.post(
        "/authn/users",
        json={"username": "op_demo", "password": "OpPass123", "role": "operator", "tenant_id": "default"},
        headers=h,
    )
    assert cu.status_code == 200
    assert cu.json()["user"]["role"] == "OPERATOR"
    lst = await client.get("/authn/users", headers=h)
    assert lst.status_code == 200
    assert any(u["username"] == "op_demo" for u in lst.json()["users"])


async def test_rbac_viewer_cannot_set_role(client):
    tok = (await client.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})).json()["access_token"]
    h = _auth_header(tok)
    # 建一个 viewer
    await client.post(
        "/authn/users", json={"username": "viewer_demo", "password": "VpPass123", "role": "viewer"}, headers=h
    )
    # viewer 登录
    vtok = (await client.post("/authn/login", json={"username": "viewer_demo", "password": "VpPass123"})).json()["access_token"]
    vh = _auth_header(vtok)
    # viewer 看用户列表应被 403（需 tenant_admin 及以上）
    assert (await client.get("/authn/users", headers=vh)).status_code == 403
    # viewer 改角色应 403
    assert (await client.post("/authn/users/whatever/role", json={"role": "superadmin"}, headers=vh)).status_code == 403


async def test_backends_status(client):
    tok = (await client.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})).json()["access_token"]
    r = await client.get("/authn/backends", headers=_auth_header(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["local"]["enabled"] is True
    assert "ldap" in body and "oauth2" in body and "saml" in body


@pytest.mark.asyncio
async def test_global_gate_dev_mode_allows_anonymous(client):
    """开发/测试模式（ZHIYAN_AUTH_REQUIRE 未开）：受保护端点无 token 也应 200。"""
    from src.runtime.authn.config import config

    config.REQUIRE_AUTH = False
    # /auth/boundaries 受 require_auth 门禁保护
    r = await client.get("/auth/boundaries")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_global_gate_prod_mode_enforces(client):
    """生产模式（ZHIYAN_AUTH_REQUIRE=1）：无 token → 401；有效 token → 200。"""
    from src.runtime.authn.config import config

    config.REQUIRE_AUTH = True
    try:
        r401 = await client.get("/auth/boundaries")
        assert r401.status_code == 401
        # 有效 token 放行
        tok = (await client.post("/authn/login", json={"username": "admin", "password": TEST_ADMIN_PW})).json()["access_token"]
        r200 = await client.get("/auth/boundaries", headers=_auth_header(tok))
        assert r200.status_code == 200
    finally:
        config.REQUIRE_AUTH = False
