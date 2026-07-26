"""认证服务——组合本地/LDAP/OAuth2 后端，签发 JWT，管理用户与 RBAC

单例 `authn_service` 在进程内维护：
- 内存用户注册表 `_mem`（DB 不可用或测试时的降级存储，以及管理员种子）
- DB users 表（db 可用时的持久化，重启不丢）

登录链路（韧性降级）：
    LocalBackend → (LDAP mock/real) → 失败
目录(LDAP/OAuth2)用户首次登录自动在本地建账号（auth_source=ldap/oauth2，无本地密码），
后续登录走目录校验，RBAC 角色按本地记录生效。

JWT 由 security.encode_jwt 签发，payload 含 sub/uid/role/tenant_id/auth_source。
"""

import logging
import secrets
import uuid

from src.common import db
from src.runtime.authn import backends
from src.runtime.authn.config import config
from src.runtime.authn.models import User
from src.runtime.authn.roles import Role, parse_role, has_role
from src.runtime.authn.security import encode_jwt, hash_password, verify_password

logger = logging.getLogger("zhiyan.authn")


class AuthnService:
    def __init__(self):
        self._mem: dict[str, dict] = {}  # username -> user dict
        self._seeded = False
        # 后端：本地永远在；LDAP 按配置（含 mock）；OAuth2 按配置
        self._local = backends.LocalBackend(self._local_check)
        self._ldap = backends.MockLDAPBackend() if config.LDAP_MOCK else backends.LDAPBackend()
        self._oauth = backends.OAuth2Backend()
        self._saml = backends.SAMLBackend()

    # ---------------- 存储抽象 ----------------

    async def _find_db(self, username: str) -> User | None:
        if not (db.db_available and db.async_session):
            return None
        try:
            from sqlalchemy import select

            async with db.async_session() as s:
                return (await s.execute(select(User).where(User.username == username))).scalars().first()
        except Exception as e:
            logger.warning(f"查询用户失败（回退内存）：{e}")
            return None

    async def _upsert_db(self, rec: dict) -> None:
        if not (db.db_available and db.async_session):
            return
        try:
            async with db.async_session() as s:
                existing = (
                    await s.execute(select(User).where(User.username == rec["username"]))
                ).scalars().first()
                if existing:
                    for k, v in rec.items():
                        if k in ("id", "username"):
                            continue
                        setattr(existing, k, v)
                else:
                    s.add(User(**rec))
                await s.commit()
        except Exception as e:
            logger.warning(f"落库用户失败（仅内存态）：{e}")

    async def _load(self, username: str) -> dict | None:
        u = await self._find_db(username)
        if u is not None:
            return u.to_dict(include_secrets=True)
        return self._mem.get(username)

    async def _list_db(self, tenant_id: str | None) -> list[dict]:
        if not (db.db_available and db.async_session):
            return []
        try:
            from sqlalchemy import select

            async with db.async_session() as s:
                q = select(User)
                if tenant_id:
                    q = q.where(User.tenant_id == tenant_id)
                rows = (await s.execute(q)).scalars().all()
                return [r.to_dict() for r in rows]
        except Exception:
            return []

    # ---------------- 管理员种子 ----------------

    async def ensure_admin(self, password: str | None = None) -> dict:
        """确保超级管理员存在（幂等）。password 覆盖 env，主要用于测试确定性。"""
        pw = password if password is not None else (config.ADMIN_PASSWORD or secrets.token_urlsafe(12))
        if config.ADMIN_PASSWORD and password is None:
            pw = config.ADMIN_PASSWORD
        rec = {
            "id": uuid.uuid4().hex[:12],
            "username": config.ADMIN_USERNAME,
            "email": config.ADMIN_EMAIL,
            "display_name": "平台管理员",
            "password_hash": hash_password(pw),
            "role": Role.SUPERADMIN,
            "tenant_id": "default",
            "auth_source": "local",
            "is_active": True,
            "external_id": None,
        }
        # 已存在则跳过（保留既有密码）
        existing = await self._load(config.ADMIN_USERNAME)
        if existing:
            self._seeded = True
            return existing
        self._mem[rec["username"]] = rec
        await self._upsert_db(rec)
        self._seeded = True
        if password is None and not config.ADMIN_PASSWORD:
            logger.warning(f"⚠️ 已生成开发管理员账号 {config.ADMIN_USERNAME} / 密码: {pw} （生产请配置 ZHIYAN_ADMIN_PASSWORD）")
        else:
            logger.info(f"✅ 管理员账号就绪：{config.ADMIN_USERNAME}（角色 SUPERADMIN）")
        return rec

    # ---------------- 本地校验（供 LocalBackend 回调）----------------

    def _local_check(self, username: str, password: str) -> dict | None:
        """同步回调：返回匹配的用户档案或 None。仅对本地用户校验密码。"""
        # 先内存
        rec = self._mem.get(username)
        if rec is None:
            # 异步 DB 查询无法在同步回调里做；但 ensure_admin 已把种子写内存，
            # 目录用户也已写内存。DB-only 用户由 authenticate 的异步预载覆盖。
            return None
        if not rec.get("is_active", True):
            return None
        if rec.get("auth_source") != "local":
            return None  # 目录用户不在本地校验密码
        if verify_password(password, rec.get("password_hash") or ""):
            return rec
        return None

    async def _preload_local(self, username: str) -> None:
        """把 DB 中的本地用户预载进内存，使同步 _local_check 能命中。"""
        u = await self._find_db(username)
        if u and u.auth_source == "local":
            self._mem[u.username] = u.to_dict(include_secrets=True)

    # ---------------- 登录 ----------------

    async def authenticate(self, username: str, password: str) -> dict | None:
        """返回 {access_token, token_type, user} 或 None（全部后端拒绝）。"""
        await self.ensure_admin()
        await self._preload_local(username)

        # 1) 本地
        r = self._local.authenticate(username, password)
        if r.status == "ok":
            return self._issue(r.userinfo)
        if r.status == "invalid":
            # 2) 目录后端（LDAP mock/real）
            lr = self._ldap.authenticate(username, password)
            if lr.status == "ok":
                await self._provision_directory_user(lr.userinfo)
                return self._issue(lr.userinfo)
            if lr.status in ("unavailable", "error"):
                logger.info(f"LDAP 不可用（{lr.detail}），仅本地认证")
        return None

    async def authenticate_oauth_code(self, code: str, redirect_uri: str | None = None) -> dict | None:
        """OAuth2 授权码登录。"""
        await self.ensure_admin()
        r = await self._oauth.exchange(code, redirect_uri)
        if r.status == "ok":
            await self._provision_directory_user(r.userinfo)
            return self._issue(r.userinfo)
        logger.info(f"OAuth2 登录失败：{r.detail}")
        return None

    async def _provision_directory_user(self, info: dict) -> None:
        """目录用户首次登录自动建本地账号（无密码，角色取默认目录角色）。"""
        existing = await self._load(info["username"])
        if existing:
            return
        rec = {
            "id": uuid.uuid4().hex[:12],
            "username": info["username"],
            "email": info.get("email"),
            "display_name": info.get("display_name"),
            "password_hash": None,
            "role": parse_role(config.DEFAULT_DIR_ROLE),
            "tenant_id": "default",
            "auth_source": info.get("auth_source", "ldap"),
            "is_active": True,
            "external_id": info.get("external_id"),
        }
        self._mem[rec["username"]] = rec
        await self._upsert_db(rec)
        logger.info(f"🆕 目录用户已自动建号：{rec['username']}（{rec['auth_source']}）")

    def _issue(self, info: dict) -> dict:
        role = info.get("role", "operator")
        try:
            role_name = parse_role(role).name
        except Exception:
            role_name = "OPERATOR"
        token = encode_jwt(
            {
                "sub": info["username"],
                "uid": info.get("id") or info["username"],
                "role": role_name,
                "tenant_id": info.get("tenant_id", "default"),
                "auth_source": info.get("auth_source", "local"),
                "name": info.get("display_name") or info["username"],
            }
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "username": info["username"],
                "display_name": info.get("display_name") or info["username"],
                "role": role_name,
                "tenant_id": info.get("tenant_id", "default"),
                "auth_source": info.get("auth_source", "local"),
            },
        }

    # ---------------- Token 解析 ----------------

    def get_user_from_token(self, token: str) -> dict | None:
        from src.runtime.authn.security import decode_jwt

        try:
            p = decode_jwt(token)
        except ValueError:
            return None
        return {
            "username": p.get("sub"),
            "uid": p.get("uid"),
            "role": p.get("role", "OPERATOR"),
            "tenant_id": p.get("tenant_id", "default"),
            "auth_source": p.get("auth_source", "local"),
            "display_name": p.get("name", p.get("sub")),
        }

    # ---------------- 用户管理（RBAC 由 API 层 require_role 保护）----------------

    async def create_user(
        self, username: str, password: str, role: str = "operator",
        tenant_id: str = "default", email: str | None = None, display_name: str | None = None,
    ) -> dict:
        if await self._load(username):
            raise ValueError(f"用户已存在: {username}")
        rec = {
            "id": uuid.uuid4().hex[:12],
            "username": username,
            "email": email,
            "display_name": display_name or username,
            "password_hash": hash_password(password),
            "role": parse_role(role),
            "tenant_id": tenant_id,
            "auth_source": "local",
            "is_active": True,
            "external_id": None,
        }
        self._mem[rec["username"]] = rec
        await self._upsert_db(rec)
        return self._public(rec)

    async def list_users(self, tenant_id: str | None = None) -> list[dict]:
        db_list = await self._list_db(tenant_id)
        seen = {u["username"] for u in db_list}
        mem_list = [v for v in self._mem.values() if v["username"] not in seen]
        if tenant_id:
            mem_list = [v for v in mem_list if v.get("tenant_id") == tenant_id]
        out = [u for u in (db_list + mem_list)]
        return [self._public(u) for u in out]

    async def get_user(self, user_id: str) -> dict | None:
        # 内存 + DB 查找
        for u in self._mem.values():
            if u["id"] == user_id:
                return self._public(u)
        if db.db_available and db.async_session:
            try:
                from sqlalchemy import select

                async with db.async_session() as s:
                    row = (await s.execute(select(User).where(User.id == user_id))).scalars().first()
                    if row:
                        return self._public(row.to_dict())
            except Exception:
                pass
        return None

    async def set_role(self, user_id: str, role: str) -> dict:
        role_enum = parse_role(role)
        rec = None
        for u in self._mem.values():
            if u["id"] == user_id:
                u["role"] = role_enum
                rec = u
                break
        if db.db_available and db.async_session:
            try:
                from sqlalchemy import select

                async with db.async_session() as s:
                    row = (await s.execute(select(User).where(User.id == user_id))).scalars().first()
                    if row:
                        row.role = role_enum
                        await s.commit()
                        rec = row.to_dict(include_secrets=True)
            except Exception as e:
                logger.warning(f"更新角色落库失败：{e}")
        if rec is None:
            raise ValueError("用户不存在")
        return self._public(rec)

    @staticmethod
    def _public(rec: dict) -> dict:
        d = dict(rec)
        d.pop("password_hash", None)
        if isinstance(d.get("role"), Role):
            d["role"] = d["role"].name
        return d

    # ---------------- RBAC ----------------

    @staticmethod
    def check_role(current_role: str, min_role: str) -> bool:
        return has_role(current_role, min_role)


authn_service = AuthnService()
