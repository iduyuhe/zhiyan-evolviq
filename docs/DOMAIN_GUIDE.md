# 稳定域名配置指引

> 当前对外地址为裸 IP `http://43.153.172.52:3006`，影响专业度与分享体验。本文档给出将其替换为稳定域名的三种方案，按推荐度排序。所有操作均在**用户侧 / 服务器侧**完成，不涉及代码改动（平台已通过 nginx 反代 `/api` → `runtime:8000`，仅需前端入口域名化）。

---

## 方案 A（推荐）：自有域名 + Cloudflare 代理 + Let's Encrypt

**适用**：已有域名，想要 HTTPS + CDN 加速 + 免费证书。

### 1. DNS 解析
在域名控制台（如阿里云 / 腾讯云 / Cloudflare）添加：
```
类型  名称        值               代理状态
A     @           43.153.172.52    Proxied（橙色云）
CNAME www         你的域名.com      Proxied
```
> Cloudflare 代理后，源站 IP 被隐藏，且自动提供 HTTPS。

### 2. 服务器端 nginx（替换现有 `cjgc.conf` 之外的独立 conf）
```nginx
# /etc/nginx/conf.d/zhiyan.conf
server {
    listen 80;
    server_name zhiyan.yourdomain.com www.zhiyan.yourdomain.com;
    # 让 certbot 验证用
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl;
    server_name zhiyan.yourdomain.com www.zhiyan.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/zhiyan.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zhiyan.yourdomain.com/privkey.pem;

    # 前端 studio（容器内 nginx 已在 3006 提供，这里反代）
    location / {
        proxy_pass http://127.0.0.1:3006;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    # API 已由 studio 容器内 nginx 反代 /api → runtime:8000，无需重复
}
```

### 3. 申请证书
```bash
certbot --nginx -d zhiyan.yourdomain.com -d www.zhiyan.yourdomain.com
```

### 4. 验证
```
curl -I https://zhiyan.yourdomain.com/api/health
# 期望：HTTP/2 200
```

---

## 方案 B：自有域名 + 服务器原生 nginx（无 Cloudflare）

**适用**：不想用 Cloudflare，直接解析到服务器。

DNS 用 **DNS only（灰色云）** 的 A 记录指向 `43.153.172.52`，nginx 配置同上（去掉 Cloudflare 相关），证书仍用 certbot。

> ⚠️ 注意：服务器 80 端口当前被主机 nginx `cjgc.conf` 占用（`listen 80`）。新增 `zhiyan.conf` 时**不要重复 `listen 80` 同名 server_name**，用不同 `server_name` 即可共存，无需动 cjgc。

---

## 方案 C：临时 / 内网演示（不推荐长期）

使用动态 DNS（如 `duckdns.org`）或 Cloudflare Tunnel：
```bash
# Cloudflare Tunnel，无需开放端口
cloudflared tunnel --url http://localhost:3006
```
适合临时客户演示，域名形如 `zhiyan.trycloudflare.com`。

---

## 安全组 / 防火墙

域名化后，建议**收紧入站**：
- 仅放行 `80 / 443`（对外）
- 关闭 `3006` 公网暴露（改 `docker-compose` 端口映射为 `127.0.0.1:3006:3006`，仅本机 nginx 可达）
- `8000`（runtime）始终保持容器内，不公网暴露

---

## 验证清单

- [ ] DNS 生效（`dig zhiyan.yourdomain.com` 返回 `43.153.172.52`）
- [ ] HTTPS 可访问（`https://zhiyan.yourdomain.com` 显示控制台）
- [ ] API 正常（`/api/health` 返回 200）
- [ ] 3006 端口公网不可达（仅 443 入口）
- [ ] 证书自动续期（`certbot renew --dry-run` 通过）

---

*域名与证书为基础设施层操作，不影响智衍 EvolvIQ 代码。配置完成后续将 `README` 与白皮书中的裸 IP 替换为正式域名即可。*
