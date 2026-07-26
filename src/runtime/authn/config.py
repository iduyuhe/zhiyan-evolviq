"""企业认证配置——从环境变量读取（韧性：缺省即可降级为本地模式）

LDAP：
  AUTH_LDAP_ENABLED=1           启用 LDAP 后端
  AUTH_LDAP_SERVER=ldap://ad.corp.com:389
  AUTH_LDAP_BIND_DN=cn=svc,dc=corp,dc=com
  AUTH_LDAP_BIND_PASSWORD=***
  AUTH_LDAP_BASE_DN=dc=corp,dc=com
  AUTH_LDAP_USER_FILTER=(sAMAccountName={user})   # {user} 占位用户名
  AUTH_LDAP_USE_SSL=0/1
  AUTH_LDAP_MOCK=1              离线演示：用 AUTH_LDAP_MOCK_USERS 冒充 AD
  AUTH_LDAP_MOCK_USERS=alice:Pass123,bob:Pass456

OAuth2（通用，适配 Azure AD / 企业微信 / 飞书 / Keycloak）：
  OAUTH_ENABLED=1
  OAUTH_AUTHORIZE_URL=https://login.microsoftonline.com/.../oauth2/v2.0/authorize
  OAUTH_TOKEN_URL=https://login.microsoftonline.com/.../oauth2/v2.0/token
  OAUTH_USERINFO_URL=https://graph.microsoft.com/v1.0/me
  OAUTH_CLIENT_ID=***
  OAUTH_CLIENT_SECRET=***
  OAUTH_SCOPE=openid profile email
  OAUTH_REDIRECT_URI=https://your-domain/authn/oauth/callback

SAML：当前为可插拔占位（见 backends.SAMLBackend），生产需集成 python3-saml。
"""

import os


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip() in ("1", "true", "True", "yes")


class AuthnConfig:
    # ---- 管理员种子 ----
    ADMIN_USERNAME = os.getenv("ZHIYAN_ADMIN_USERNAME", "admin")
    ADMIN_EMAIL = os.getenv("ZHIYAN_ADMIN_EMAIL", "admin@zhiyan.local")
    # 缺省管理员密码仅在开发期使用；生产必须由 install.sh 注入 ZHIYAN_ADMIN_PASSWORD
    ADMIN_PASSWORD = os.getenv("ZHIYAN_ADMIN_PASSWORD", "")

    # ---- LDAP ----
    LDAP_ENABLED = _flag("AUTH_LDAP_ENABLED")
    LDAP_SERVER = os.getenv("AUTH_LDAP_SERVER", "")
    LDAP_BIND_DN = os.getenv("AUTH_LDAP_BIND_DN", "")
    LDAP_BIND_PASSWORD = os.getenv("AUTH_LDAP_BIND_PASSWORD", "")
    LDAP_BASE_DN = os.getenv("AUTH_LDAP_BASE_DN", "")
    LDAP_USER_FILTER = os.getenv("AUTH_LDAP_USER_FILTER", "(sAMAccountName={user})")
    LDAP_USE_SSL = _flag("AUTH_LDAP_USE_SSL")
    LDAP_MOCK = _flag("AUTH_LDAP_MOCK")
    LDAP_MOCK_USERS = os.getenv("AUTH_LDAP_MOCK_USERS", "alice:Pass123,bob:Pass456")

    # ---- OAuth2 ----
    OAUTH_ENABLED = _flag("OAUTH_ENABLED")
    OAUTH_AUTHORIZE_URL = os.getenv("OAUTH_AUTHORIZE_URL", "")
    OAUTH_TOKEN_URL = os.getenv("OAUTH_TOKEN_URL", "")
    OAUTH_USERINFO_URL = os.getenv("OAUTH_USERINFO_URL", "")
    OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "")
    OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
    OAUTH_SCOPE = os.getenv("OAUTH_SCOPE", "openid profile email")
    OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "")

    # 默认新用户角色（目录同步来的用户默认操作员）
    DEFAULT_DIR_ROLE = os.getenv("ZHIYAN_DEFAULT_DIR_ROLE", "operator")

    # ---- 全局鉴权强制开关 ----
    # 生产设 ZHIYAN_AUTH_REQUIRE=1 强制所有受保护路由须持 Bearer JWT；
    # 开发/测试默认关闭，避免破坏 150+ 既有测试与不带 token 的 e2e 脚本。
    REQUIRE_AUTH = _flag("ZHIYAN_AUTH_REQUIRE")

    @classmethod
    def ldap_mock_users(cls) -> dict[str, str]:
        out = {}
        for pair in cls.LDAP_MOCK_USERS.split(","):
            pair = pair.strip()
            if not pair:
                continue
            u, _, p = pair.partition(":")
            if u:
                out[u.strip()] = p
        return out


config = AuthnConfig()
