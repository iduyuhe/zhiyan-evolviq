"""认证后端——本地 / LDAP（含离线 Mock）/ OAuth2 / SAML(占位)

统一返回类型：AuthenticateResult
    ok         -> 凭证有效，返回用户档案（用于本地同步 + 签发 JWT）
    unavailable-> 该后端未配置 / 依赖缺失，调用方应回退下一后端
    invalid    -> 凭证错误
    error      -> 后端异常（网络/配置），记日志但不阻断整体登录

设计原则（韧性降级）：任何一个后端失败都绝不抛异常中断登录流程，
而是返回 unavailable/error 让 AuthnService 决定回退。
"""

import logging
from dataclasses import dataclass
from typing import Callable

from src.runtime.authn.config import config

logger = logging.getLogger("zhiyan.authn")


@dataclass
class AuthResult:
    status: str  # ok | unavailable | invalid | error
    userinfo: dict | None = None
    detail: str = ""


# 本地用户校验回调类型：(username, password) -> userinfo|None
LocalCheck = Callable[[str, str], dict | None]


class LocalBackend:
    """校验本地 users 表（或内存注册表）。userinfo 来自 service 注入的查询函数。"""

    name = "local"

    def __init__(self, local_check: LocalCheck):
        self._check = local_check

    def authenticate(self, username: str, password: str) -> AuthResult:
        try:
            info = self._check(username, password)
            if info is None:
                return AuthResult("invalid", detail="本地用户不存在或密码错误")
            return AuthResult("ok", info)
        except Exception as e:  # pragma: no cover - 防御性
            logger.warning(f"本地认证异常：{e}")
            return AuthResult("error", detail=str(e))


class MockLDAPBackend:
    """离线演示用 LDAP：用 AUTH_LDAP_MOCK_USERS 冒充企业 AD，无需真实目录。"""

    name = "ldap(mock)"

    def __init__(self, users: dict[str, str] | None = None):
        self._users = users if users is not None else config.ldap_mock_users()

    def authenticate(self, username: str, password: str) -> AuthResult:
        if username in self._users and self._users[username] == password:
            return AuthResult(
                "ok",
                {
                    "username": username,
                    "email": f"{username}@mock-ad.local",
                    "display_name": username,
                    "external_id": f"mockldap:{username}",
                    "auth_source": "ldap",
                },
            )
        return AuthResult("invalid", detail="MockLDAP 凭证错误")


class LDAPBackend:
    """真实企业 AD/LDAP 认证（python-ldap）。依赖缺失或未配置时返回 unavailable。

    连接流程：用服务账号 bind → 按 user_filter 搜出用户 dn → 用用户 dn + 密码 rebind 校验。
    """

    name = "ldap"

    def __init__(self):
        self._cfg_ok = bool(
            config.LDAP_ENABLED
            and config.LDAP_SERVER
            and config.LDAP_BIND_DN
            and config.LDAP_BASE_DN
        )

    def authenticate(self, username: str, password: str) -> AuthResult:
        if not self._cfg_ok:
            return AuthResult("unavailable", detail="LDAP 未启用或未配置")
        try:
            import ldap  # 惰性导入：未装 python-ldap 时不崩溃
        except ImportError:
            return AuthResult("unavailable", detail="python-ldap 未安装（pip install python-ldap）")

        try:
            # 1) 服务账号 bind
            conn = ldap.initialize(config.LDAP_SERVER)
            conn.set_option(ldap.OPT_REFERRALS, 0)
            if config.LDAP_USE_SSL:
                conn.start_tls_s()
            conn.simple_bind_s(config.LDAP_BIND_DN, config.LDAP_BIND_PASSWORD)

            # 2) 搜出用户 dn
            flt = config.LDAP_USER_FILTER.replace("{user}", username)
            res = conn.search_s(config.LDAP_BASE_DN, ldap.SCOPE_SUBTREE, flt, ["mail", "displayName"])
            if not res:
                return AuthResult("invalid", detail="LDAP 用户不存在")
            user_dn, attrs = res[0]
            mail = attrs.get("mail", [b""])[0].decode("utf-8", "ignore") or f"{username}@{config.LDAP_BASE_DN}"
            display = attrs.get("displayName", [b""])[0].decode("utf-8", "ignore") or username

            # 3) 用用户 dn + 密码 rebind 校验
            conn.simple_bind_s(user_dn, password)
            conn.unbind_s()
            return AuthResult(
                "ok",
                {
                    "username": username,
                    "email": mail,
                    "display_name": display,
                    "external_id": f"ldap:{user_dn}",
                    "auth_source": "ldap",
                },
            )
        except ldap.INVALID_CREDENTIALS:
            return AuthResult("invalid", detail="LDAP 凭证错误")
        except Exception as e:
            logger.warning(f"LDAP 认证异常：{e}")
            return AuthResult("error", detail=str(e))


class OAuth2Backend:
    """通用 OAuth2 授权码流程（适配 Azure AD / 企业微信 / 飞书 / Keycloak）。

    只用标准库 + httpx（httpx 已在依赖中）。未配置时 unavailable。
    """

    name = "oauth2"

    def __init__(self):
        self._cfg_ok = bool(
            config.OAUTH_ENABLED
            and config.OAUTH_TOKEN_URL
            and config.OAUTH_CLIENT_ID
        )

    async def exchange(self, code: str, redirect_uri: str | None = None) -> AuthResult:
        """用授权码换取 token + userinfo。"""
        if not self._cfg_ok:
            return AuthResult("unavailable", detail="OAuth2 未启用或未配置")
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return AuthResult("unavailable", detail="httpx 未安装")

        ruri = redirect_uri or config.OAUTH_REDIRECT_URI
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                tok = await c.post(
                    config.OAUTH_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": config.OAUTH_CLIENT_ID,
                        "client_secret": config.OAUTH_CLIENT_SECRET,
                        "redirect_uri": ruri,
                    },
                )
                tok.raise_for_status()
                access = tok.json().get("access_token")
                if not access:
                    return AuthResult("error", detail="OAuth2 未返回 access_token")
                ui_url = config.OAUTH_USERINFO_URL or config.OAUTH_AUTHORIZE_URL
                ui = await c.get(ui_url, headers={"Authorization": f"Bearer {access}"})
                ui.raise_for_status()
                u = ui.json()
                sub = u.get("sub") or u.get("id") or u.get("username") or u.get("userPrincipalName")
                return AuthResult(
                    "ok",
                    {
                        "username": (u.get("preferred_username") or u.get("userPrincipalName") or sub or "oauth_user"),
                        "email": u.get("email") or u.get("mail"),
                        "display_name": u.get("name") or u.get("displayName"),
                        "external_id": f"oauth2:{sub}",
                        "auth_source": "oauth2",
                    },
                )
        except Exception as e:
            logger.warning(f"OAuth2 交换异常：{e}")
            return AuthResult("error", detail=str(e))

    def authorize_url(self, state: str = "zhiyan") -> str | None:
        if not self._cfg_ok:
            return None
        from urllib.parse import urlencode

        q = urlencode(
            {
                "client_id": config.OAUTH_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": config.OAUTH_REDIRECT_URI,
                "scope": config.OAUTH_SCOPE,
                "state": state,
            }
        )
        return f"{config.OAUTH_AUTHORIZE_URL}?{q}"


class SAMLBackend:
    """SAML 2.0 占位后端——可插拔扩展点。

    生产接入需引入 python3-saml 并实现 SP 元数据 / ACS 端点。
    当前返回 unavailable 并在文档中说明扩展路径，不阻断其它后端。
    """

    name = "saml"

    def authenticate(self, *args, **kwargs) -> AuthResult:
        return AuthResult("unavailable", detail="SAML 后端未实现（需集成 python3-saml，见 docs/INTEGRATION_GUIDE）")
