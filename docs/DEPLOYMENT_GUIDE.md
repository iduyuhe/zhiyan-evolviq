# 智衍 EvolvIQ 部署指南

> 适用版本：v28.0+（含企业认证 / 一键部署 / 行业知识库）
> 目标读者：客户 IT 运维、实施工程师

---

## 一、环境要求

| 项目 | 最低要求 | 说明 |
|------|---------|------|
| 操作系统 | Linux (x86_64) | Ubuntu 22.04 / CentOS 8+ 验证通过 |
| Docker | 24.0+ | 含 docker compose v2 插件 |
| 内存 | 8 GB | 10 容器全栈（含 Neo4j/PG）建议 16 GB |
| 磁盘 | 20 GB 空闲 | 镜像 + 数据卷 |
| 端口 | 3006 (Web) | 反向代理入口；80/443 可选（TLS） |
| 出网 | LLM API、GitHub（拉取） | DeepSeek / 混元等 |

---

## 二、一键部署（推荐）

```bash
# 1. 取得源码
git clone https://github.com/iduyuhe/zhiyan-evolviq.git
cd zhiyan-evolviq

# 2. 交互式部署（会提问域名/管理员/DB 密码/LLM Key）
./install.sh

# 非交互（用环境变量或默认值）：
./install.sh --non-interactive

# 启用 HTTPS（自动 Let's Encrypt 证书）：
./install.sh --with-tls
```

`install.sh` 自动完成：
1. 检测 Docker / 端口可用性
2. 生成强随机密钥（管理员密码 / JWT 密钥 / DB 密码）
3. 写入 `.env`（已被 `.gitignore` 忽略，不进版本库）
4. 可选引入 Caddy 自动 ACME（`--with-tls`）
5. `docker compose up -d` 启动全栈
6. 输出访问地址与**管理员初始密码**

部署完成后访问 `http://<服务器IP>:3006`，用 `admin` + 初始密码登录。

### 非交互环境变量

| 变量 | 说明 |
|------|------|
| `ZHIYAN_DOMAIN` | 对外域名（启用 TLS 时必填） |
| `ZHIYAN_ADMIN_EMAIL` | 管理员邮箱 |
| `ZHIYAN_ADMIN_PASSWORD` | 管理员密码（建议强随机） |
| `ZHIYAN_JWT_SECRET` | JWT 签名密钥（务必固定，否则重启后旧 token 失效） |
| `ZHIYAN_DB_PASSWORD` | 数据库密码 |
| `LLM_API_KEY` / `LLM_BASE_URL` | 大模型密钥与网关地址 |

---

## 三、手动部署（docker compose）

```bash
cp .env.example .env
# 编辑 .env：补全 ZHIYAN_JWT_SECRET / ZHIYAN_ADMIN_PASSWORD / LLM_API_KEY 等
docker compose -f docker-compose.prod.yml up -d --build
```

全栈 10 个服务：`runtime`（API:8000）、`studio`（Web:3006）、`postgres`、`neo4j`、`mosquitto`、`rabbitmq`、协议模拟器（modbus/mqtt/opcua/ipc-cfx）。

---

## 四、行业知识库（可选）

通过环境变量在首次启动注入行业种子（船舶 / 铁路 / 电子）：

```bash
# .env 中设置其一
ZHIYAN_INDUSTRY=shipbuilding    # 或 railway / electronics
```

重启 runtime 容器即把对应行业的 KG 事实 / 本体扩展 / 隐性经验样例注入三大回路（均为「提议」待审批门把关，不会自动生效）。

---

## 五、启停与运维

```bash
docker compose -f docker-compose.prod.yml ps           # 状态
docker compose -f docker-compose.prod.yml logs -f runtime   # 看日志
docker compose -f docker-compose.prod.yml restart runtime   # 重启 API
docker compose -f docker-compose.prod.yml down          # 停止
```

### 升级

```bash
git fetch origin && git reset --hard origin/main
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 六、备份与恢复

| 数据 | 容器/卷 | 备份方式 |
|------|--------|---------|
| 业务库 | `zhiyan-postgres` 卷 `pgdata` | `docker exec zhiyan-postgres pg_dump -U zhiyan zhiyan > zhiyan_$(date +%F).sql` |
| 知识图谱 | `zhiyan-neo4j` 卷 `neo4jdata` | `docker exec zhiyan-neo4j neo4j-admin database dump neo4j` |
| 配置 | `.env` | 复制文件（**含密钥，单独加密保管**） |

建议每日凌晨 cron 执行 PG dump + 配置文件快照。

---

## 七、常见问题

- **登录后 token 重启即失效** → `.env` 未固定 `ZHIYAN_JWT_SECRET`，请生成固定值并重启 runtime。
- **忘记管理员密码** → 直连 PG 删除 `authn_users` 表中 `admin` 行，重启后自动用 `ZHIYAN_ADMIN_PASSWORD` 重建；或直接改 `.env` 中该值后重启。
- **端口被占用** → 3006 不可与宿主机其他服务冲突，改 `docker-compose.prod.yml` 映射端口即可。
- **LLM 调用失败** → 检查 `LLM_API_KEY`/`LLM_BASE_URL` 出网；无 LLM 时平台降级运行（决策辅助为空，其余功能正常）。
