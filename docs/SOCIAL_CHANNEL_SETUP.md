# 社交通道密钥获取 + 填写操作手册（阶段 6.1 · 隐性捕获 演示态 → 生产态）

> 配套：`PRODUCT_DEVELOPMENT_PLAN.md` §2.1(6.1) / `GAP_REVIEW_v29.md` 缺口 B / `ECOSYSTEM_LAUNCH.md`
> 一句话：**代码已上线（v29.9），三个连接器已挂在系统里，但现在全是"锁着"的状态（`enabled=false`），因为没钥匙。本手册教您去各平台后台"拿钥匙"→ 填到服务器 → 系统就开始真正"听"您的群和邮件。**

---

## 0. 当前状态（您接手前）

| 连接器 | 代码位置 | 生产状态 | 卡在哪 |
|---|---|---|---|
| 企业微信 | `src/runtime/connectors/wecom_ingest.py` | `enabled=false` | 缺 `wecom_token` 等 |
| 钉钉 | `src/runtime/connectors/dingtalk_ingest.py` | `enabled=false` | 缺 `dingtalk_secret` |
| 邮件 | `src/runtime/connectors/email_ingest.py` | `enabled=false` | 缺 `email_imap_*` |

- 生产地址：`http://43.153.172.52:3006`
- 后端 API 前缀：`/api`（nginx 已自动剥离，您写完整 URL 即可）
- 管理端点（需登录 JWT）：`GET /api/connectors`、`GET /api/connectors/{name}/test`
- 外部回调端点（平台调，免 JWT）：`/api/connectors/wecom/callback`、`/api/connectors/dingtalk/callback`

---

## ⚠️ 1. 先读这个：HTTPS 回调约束（很重要）

企业微信、钉钉的"接收消息"回调 **强制要求 HTTPS**（公网回调地址必须是 `https://` 开头）。当前生产是 **HTTP**（`http://43.153.172.52:3006`）。所以：

- **正式上线**：需要给服务器配 HTTPS（域名 + 证书）。我可以帮您在 nginx 上加 Let's Encrypt 免费证书——但需您提供一个域名（如 `zhiyan.您的域名.com`）并做 DNS 解析。
- **先测通**：不想现在动证书，可用内网穿透（frp / ngrok / cpolar）临时拿一个 `https://` 回调地址，把连接器调通验证逻辑；正式再换域名。

> 邮件通道不受此限（IMAP 是系统主动去邮箱拉，不需要公网回调），可立即配。

---

## 2. 通道一：企业微信（自建应用）

### 2.1 去哪拿钥匙（企业微信管理后台）
1. 登录 [企业微信管理后台](https://work.weixin.qq.com/) → **应用管理 → 自建 → 创建应用**（或选已有应用）。
2. 进入应用 → **接收消息 → 设置 API 接收**：
   - **URL**：填 `https://<您的域名或穿透地址>/api/connectors/wecom/callback`
   - **Token**：点"随机生成"，复制这串（这就是 `wecom_token`）
   - **EncodingAESKey**：点"随机生成"，复制这串（这就是 `wecom_aes_key`）
3. 应用详情页顶部 **CorpID（企业ID）**：复制（这就是 `wecom_corp_id`）。

### 2.2 填到哪（服务器 `/root/zhiyan/.env`）
```ini
ZHIYAN_WECOM_TOKEN=第2.1步生成的Token
ZHIYAN_WECOM_AES_KEY=第2.1步生成的EncodingAESKey
ZHIYAN_WECOM_CORP_ID=企业CorpID
```
> **最小启用**：只填 `ZHIYAN_WECOM_TOKEN` 即可让连接器 `enabled=true`（URL 验证通过）。要能**解密群消息正文**，三项必须都填。

### 2.3 验证
企微后台点"保存"时会自动发一次 URL 验证 GET 请求；系统返回明文 `echostr` 即成功。也可登录系统后：
```bash
curl -H "Authorization: Bearer <您的JWT>" \
  http://43.153.172.52:3006/api/connectors/wecom/test
# 期望返回 {"ok": true, ...}
```

---

## 3. 通道二：钉钉（连接平台 / 群机器人加签）

### 3.1 去哪拿钥匙（钉钉开发者后台）
1. 登录 [钉钉开放平台](https://open.dingtalk.com/) → **应用开发 → 创建应用**（或已有应用）。
2. 应用 → **事件订阅**：
   - **请求地址**：填 `https://<您的域名或穿透地址>/api/connectors/dingtalk/callback`
   - **加签密钥（AppSecret / 签名秘钥）**：复制这串（这就是 `dingtalk_secret`）
3. （可选）**AppKey / AppSecret**：若走"连接平台"授权流才需要，加签机器人只需 `secret`。

### 3.2 填到哪
```ini
ZHIYAN_DINGTALK_SECRET=第3.1步的加签密钥
# 以下两项仅在走连接平台授权流时填，纯加签群机器人可留空
ZHIYAN_DINGTALK_APP_KEY=
ZHIYAN_DINGTALK_APP_SECRET=
```
> **最小启用**：只填 `ZHIYAN_DINGTALK_SECRET` 即可 `enabled=true`。

### 3.3 验证
```bash
curl -H "Authorization: Bearer <您的JWT>" \
  http://43.153.172.52:3006/api/connectors/dingtalk/test
```

---

## 4. 通道三：邮件（IMAP 轮询，无需公网，可立即配）

### 4.1 去哪拿钥匙
以**企业邮箱 / QQ 邮箱**为例：
1. 登录邮箱网页版 → **设置 → 账户 → 开启 IMAP/SMTP 服务**。
2. 按提示用手机发短信或扫码，**生成"授权码"**（不是邮箱登录密码！第三方客户端必须用授权码）。
3. 记下：IMAP 服务器地址（如 `imap.exmail.qq.com` 或 `imap.qq.com`）、完整邮箱地址、刚生成的授权码。

### 4.2 填到哪
```ini
ZHIYAN_EMAIL_IMAP_HOST=imap.exmail.qq.com
ZHIYAN_EMAIL_IMAP_USER=production@您的企业.com
ZHIYAN_EMAIL_IMAP_PASSWORD=邮箱授权码（非登录密码）
ZHIYAN_EMAIL_IMAP_MAILBOX=INBOX
ZHIYAN_EMAIL_POLL_INTERVAL=300
```
> **最小启用**：`HOST` + `USER` + `PASSWORD` 三项都填即 `enabled=true`。系统每 `POLL_INTERVAL` 秒自动拉一次未读邮件。

### 4.3 验证
```bash
# 手动触发一次拉取
curl -X POST -H "Authorization: Bearer <您的JWT>" \
  http://43.153.172.52:3006/api/connectors/email/pull
# 期望返回 {"pulled": N, "published": M, "sensitive": K, ...}
```

---

## 5. 填完后：让配置生效

`.env` 改动后**必须重启 runtime 容器**才能加载新密钥：
```bash
cd /root/zhiyan && docker compose -f docker-compose.prod.yml up -d runtime
```
重启后访问 `http://43.153.172.52:3006/` → 登录 → 左侧「连接」tab → 社交通道区应显示对应通道 `enabled=true`，并可点"测试"。

---

## 6. 安全须知
- 密钥只在**服务器 `/root/zhiyan/.env`** 里，不进 Git（仓库已 gitignore `.env`）。
- 不要在微信/聊天里直接发明文密钥给我；若需我帮配，走服务器安全通道或由您自己粘贴。
- 企微/钉钉回调靠**签名鉴权**（非 JWT），即便公网暴露也只有持正确密钥的平台能推送成功，伪造请求会被 403 拒。

---

## 7. 故障排查

| 现象 | 可能原因 | 处置 |
|---|---|---|
| `/api/connectors` 显示 `enabled=false` | `.env` 字段没填全 / 没重启 | 补齐字段 + 重启 runtime |
| 企微保存回调时报"URL 验证失败" | 回调地址非 HTTPS / 服务不可达 | 见 §1，配 HTTPS 或穿透 |
| 企微 `enabled=true` 但收不到消息 | 只填了 token，缺 aes_key/corp_id | 补齐三项 |
| 钉钉 `test` 报 403 | secret 填错 | 核对加签密钥 |
| 邮件 `pulled=0` | 授权码错 / IMAP 未开 / 邮箱无未读 | 重生成授权码；先发一封测试邮件 |

---

*配齐任一通道后，系统在群/邮件里抓到的生产经验就会自动进"隐性捕获 → 经验库 + 知识图谱"，决策脑开始吸收人的隐性知识。三个通道互相独立，配一个就转一个。*
