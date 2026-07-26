# 企业认证 API（v28）

智衍 EvolvIQ 企业认证模块提供本地账号 / LDAP(AD) / OAuth2(OIDC) 三种后端，统一签发 JWT，并按 RBAC 控制用户管理类接口。

## 一、概念

| 概念 | 说明 |
|------|------|
| 用户 (User) | 平台操作者，归属某租户，拥有单一角色 |
| 角色 (Role) | `viewer < operator < tenant_admin < superadmin` |
| 租户 (Tenant) | 多租户隔离单元，与既有 `X-Tenant-Key` 体系正交 |
| JWT | HS256 签名，默认 24h 过期，由 `ZHIYAN_JWT_SECRET` 签名 |
| 认证源 | `local` / `ldap` / `oauth2`，目录用户首登自动建号 |

## 二、认证流程

```
POST /authn/login {username, password}
  → 本地账号 → 校验 PBKDF2 哈希
  → LDAP/AD  → 绑定目录查询（离线时降级 Mock 用户）
  → 失败      → 401
  → 成功      → { access_token, user }
```

前端把 `access_token` 存于 `localStorage`，后续请求在 `Authorization: Bearer <token>` 携带。

## 三、端点清单

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/authn/login` | 否 | 用户名密码登录，返回 JWT |
| GET | `/authn/me` | 是 | 返回当前用户信息（需有效 JWT） |
| GET | `/authn/backends` | 是 | 列出已启用的认证后端（local/ldap/oauth2/saml） |
| GET | `/authn/users` | `tenant_admin+` | 列出用户 |
| POST | `/authn/users` | `tenant_admin+` | 新建本地用户 |
| POST | `/authn/users/{id}/role` | `superadmin` | 修改用户角色（RBAC 强控） |
| POST | `/authn/users/{id}/deactivate` | `tenant_admin+` | 禁用用户 |
| GET | `/authn/oauth/{provider}/login` | 否 | 跳转 OAuth2 授权页 |
| GET | `/authn/oauth/{provider}/callback` | 否 | OAuth2 回调，交换 JWT |

> 除 `/authn/*` 外，平台其余业务端点当前兼容「无 token」调用（向后兼容），全局强制 JWT 鉴权为后续 P1 任务。

## 四、RBAC 矩阵

| 操作 | viewer | operator | tenant_admin | superadmin |
|------|--------|----------|--------------|------------|
| 查看自己的信息 | ✅ | ✅ | ✅ | ✅ |
| 发起 Agent 任务 | ✅ | ✅ | ✅ | ✅ |
| 查看租户内用户 | ❌ | ❌ | ✅ | ✅ |
| 新建/禁用租户用户 | ❌ | ❌ | ✅ | ✅ |
| 修改任意用户角色 | ❌ | ❌ | ❌ | ✅ |
| 查看认证后端配置 | ❌ | ✅ | ✅ | ✅ |

代码侧通过依赖 `require_role(Role.TENANT_ADMIN)` 等守卫强制。

## 五、配置项（.env）

| 变量 | 默认 | 说明 |
|------|------|------|
| `ZHIYAN_JWT_SECRET` | 进程随机（重启失效） | JWT 签名密钥，**生产必须固定** |
| `ZHIYAN_JWT_EXPIRE` | `86400` | 过期秒数 |
| `ZHIYAN_ADMIN_USERNAME` | `admin` | 超级管理员用户名 |
| `ZHIYAN_ADMIN_PASSWORD` | 空（随机生成） | 初始密码 |
| `AUTH_LDAP_SERVER` | 空 | LDAP 服务器地址（空则后端不可用） |
| `AUTH_LDAP_BIND_DN` / `AUTH_LDAP_BIND_PASSWORD` | 空 | 目录绑定凭据 |
| `AUTH_LDAP_BASE_DN` | 空 | 搜索基 DN |
| `AUTH_LDAP_MOCK_USERS` | `alice:Pass123,bob:Pass456` | 离线 Mock 用户（无 python-ldap 时） |
| `OAUTH_AUTHORIZE_URL` / `OAUTH_TOKEN_URL` / `OAUTH_USERINFO_URL` | 空 | OIDC 端点 |
| `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` | 空 | 企业应用凭据 |
| `OAUTH_REDIRECT_URI` | 空 | 回调地址 |
| `ZHIYAN_DEFAULT_DIR_ROLE` | `operator` | 目录用户首登默认角色 |

## 六、后端降级策略

- **LDAP**：未装 `python-ldap` 或服务器不可达 → 自动降级为 Mock 用户（仅演示/离线）。
- **OAuth2**：未配置端点 → 后端在 `/authn/backends` 中不出现。
- **JWT 密钥缺失** → 进程内随机生成并告警（仅开发期，重启即失效）。

## 七、Curl 示例

```bash
# 登录
TOKEN=$(curl -s -X POST http://localhost:8000/authn/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<初始密码>"}' | jq -r .access_token)

# 查看当前用户
curl -s http://localhost:8000/authn/me -H "Authorization: Bearer $TOKEN" | jq .
```
