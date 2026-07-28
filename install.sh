#!/usr/bin/env bash
# =============================================================================
# 智衍 EvolvIQ —— 一键部署脚本（install.sh）
# -----------------------------------------------------------------------------
# 客户 IT 拿到源码后在 5 分钟内得到可登录的平台：
#   1) 检测 Docker / docker compose / 端口可用性
#   2) 交互式配置（域名 / 管理员账号 / 数据库密码 / LLM Key）
#   3) 自动生成强随机密钥（管理员密码 / JWT 密钥 / DB 密码）
#   4) 可选 HTTPS：启用后引入 Caddy 自动 ACME 证书（Let's Encrypt）
#   5) docker compose up -d 一键启动
#   6) 输出访问地址、管理员账号与密码
#
# 用法：
#   ./install.sh                 # 交互式
#   ./install.sh --non-interactive   # 用默认值 / 环境变量，不提问
#   ./install.sh --with-tls      # 启用 HTTPS（需 443 端口可达 + 真实域名）
#
# 环境变量（非交互模式可用，省去提问）：
#   ZHIYAN_DOMAIN  ZHIYAN_ADMIN_EMAIL  ZHIYAN_ADMIN_PASSWORD
#   ZHIYAN_JWT_SECRET  ZHIYAN_DB_PASSWORD  ZHIYAN_LLM_API_KEY  ZHIYAN_LLM_BASE_URL
# =============================================================================

set -euo pipefail

# ---------- 颜色 ----------
if [ -t 1 ]; then
  C_RED=$'\033[0;31m'; C_GRN=$'\033[0;32m'; C_YLW=$'\033[0;33m'; C_BLU=$'\033[0;34m'; C_RST=$'\033[0m'
else
  C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_RST=""
fi
info()  { echo "${C_BLU}[INFO]${C_RST} $*"; }
ok()    { echo "${C_GRN}[ OK ]${C_RST} $*"; }
warn()  { echo "${C_YLW}[WARN]${C_RST} $*"; }
err()   { echo "${C_RED}[ERROR]${C_RST} $*" >&2; }
die()   { err "$*"; exit 1; }

# ---------- 参数 ----------
INTERACTIVE=1
WITH_TLS=0
for a in "$@"; do
  case "$a" in
    --non-interactive) INTERACTIVE=0 ;;
    --with-tls) WITH_TLS=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
  esac
done

command -v docker >/dev/null 2>&1 || die "未检测到 docker，请先安装：https://docs.docker.com/get-docker/"
if ! docker info >/dev/null 2>&1; then
  die "docker daemon 未运行（或当前用户无权限），请启动 docker 或以 sudo 运行。"
fi
if ! docker compose version >/dev/null 2>&1; then
  die "未检测到 docker compose v2（docker compose version 失败）。"
fi
ok "Docker 与 docker compose 就绪"

# ---------- 端口检测 ----------
check_port() {
  local p="$1"
  if command -v nc >/dev/null 2>&1; then
    if nc -z 127.0.0.1 "$p" 2>/dev/null; then return 1; fi
  elif command -v python3 >/dev/null 2>&1; then
    if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.3); sys.exit(0 if s.connect_ex(('127.0.0.1',$p))==0 else 1)" 2>/dev/null; then return 1; fi
  fi
  return 0
}
for p in 80 443 3006; do
  if check_port "$p"; then
    info "端口 $p 可用"
  else
    if [ "$p" = "443" ] && [ "$WITH_TLS" -eq 1 ]; then
      warn "端口 443 已被占用 / 不可达，HTTPS 可能无法对外；仍继续。"
    else
      warn "端口 $p 已被占用（可能已有服务），部署后请确认无冲突。"
    fi
  fi
done

# ---------- 随机密钥生成 ----------
rand() {
  local n="$1"; n="${n:-24}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$((n/2))" | tr -d '\n'
  else
    python3 -c "import secrets,sys; sys.stdout.write(secrets.token_hex($((n/2))))"
  fi
}

# ---------- 交互式提问 ----------
ask() {
  # ask <prompt> <default> -> 写到全局 _ANS
  local prompt="$1" def="$2"
  if [ "$INTERACTIVE" -eq 0 ]; then _ANS="$def"; return; fi
  read -r -p "${C_YLW}${prompt}${C_RST} [$def]: " _inp
  _ANS="${_inp:-$def}"
}

# 域名 / TLS
if [ "$WITH_TLS" -eq 1 ]; then
  ask "对外域名（用于 HTTPS 证书，如 evolviq.corp.com）" "${ZHIYAN_DOMAIN:-}"
  ZHIYAN_DOMAIN="${_ANS:-$ZHIYAN_DOMAIN}"
  if [ -z "${ZHIYAN_DOMAIN:-}" ]; then
    warn "未提供域名，自动关闭 HTTPS（回退 HTTP :3006）。"
    WITH_TLS=0
  fi
else
  ask "是否启用 HTTPS（需 443 开放 + 真实域名）? [y/N]" "${ZHIYAN_DOMAIN:+y}"
  case "${_ANS,,}" in
    y|yes) WITH_TLS=1
      ask "对外域名" "${ZHIYAN_DOMAIN:-}"
      ZHIYAN_DOMAIN="$_ANS"
      ;;
    *) WITH_TLS=0 ;;
  esac
fi

ask "管理员邮箱" "${ZHIYAN_ADMIN_EMAIL:-admin@zhiyan.local}"
ZHIYAN_ADMIN_EMAIL="$_ANS"

ask "管理员密码（留空自动生成强密码）" "${ZHIYAN_ADMIN_PASSWORD:-}"
ZHIYAN_ADMIN_PASSWORD="$_ANS"
if [ -z "$ZHIYAN_ADMIN_PASSWORD" ]; then ZHIYAN_ADMIN_PASSWORD="$(rand 32)"; fi

ask "JWT 签名密钥（留空自动生成）" "${ZHIYAN_JWT_SECRET:-}"
ZHIYAN_JWT_SECRET="$_ANS"
if [ -z "$ZHIYAN_JWT_SECRET" ]; then ZHIYAN_JWT_SECRET="$(rand 48)"; fi

ask "数据库密码（留空自动生成）" "${ZHIYAN_DB_PASSWORD:-}"
ZHIYAN_DB_PASSWORD="$_ANS"
if [ -z "$ZHIYAN_DB_PASSWORD" ]; then ZHIYAN_DB_PASSWORD="$(rand 32)"; fi

ask "LLM API Key（OpenAI 兼容，留空稍后配置）" "${ZHIYAN_LLM_API_KEY:-}"
LLM_API_KEY="$_ANS"
if [ -z "$LLM_API_KEY" ]; then LLM_API_KEY="your-llm-api-key"; fi

ask "LLM Base URL" "${ZHIYAN_LLM_BASE_URL:-https://api.openai.com/v1}"
LLM_BASE_URL="$_ANS"

ask "行业知识库（shipbuilding/railway/electronics/留空=半导体默认）" "${ZHIYAN_INDUSTRY:-}"
ZHIYAN_INDUSTRY="$_ANS"

# ---------- 写 .env ----------
ENVFILE=".env"
if [ -f "$ENVFILE" ]; then
  cp "$ENVFILE" "$ENVFILE.bak.$(date +%s)"
  warn "已备份原有 $ENVFILE -> $ENVFILE.bak.*"
fi
info "生成 $ENVFILE ..."
cat > "$ENVFILE" <<EOF
# ===== 由 install.sh 生成（$(date '+%Y-%m-%d %H:%M:%S')）=====
ZHIYAN_LLM_API_KEY=$LLM_API_KEY
ZHIYAN_LLM_BASE_URL=$LLM_BASE_URL

# ===== 企业认证 =====
ZHIYAN_ADMIN_USERNAME=admin
ZHIYAN_ADMIN_EMAIL=$ZHIYAN_ADMIN_EMAIL
ZHIYAN_ADMIN_PASSWORD=$ZHIYAN_ADMIN_PASSWORD
ZHIYAN_JWT_SECRET=$ZHIYAN_JWT_SECRET

# ===== 数据库（PostgreSQL）=====
ZHIYAN_DB_URL=postgresql+asyncpg://zhiyan:$ZHIYAN_DB_PASSWORD@postgres:5432/zhiyan

# ===== 知识图谱（Neo4j）=====
NEO4J_URI=bolt://neo4j:7687
NEO4J_PASSWORD=zhiyan_dev

# ===== 行业知识库模板 =====
ZHIYAN_INDUSTRY=${ZHIYAN_INDUSTRY:-}

# ===== 演示数据（生产建议置 0）=====
ZHIYAN_DEMO_DATA=0
EOF

if [ "$WITH_TLS" -eq 1 ]; then
  echo "ZHIYAN_TLS=1" >> "$ENVFILE"
  echo "ZHIYAN_DOMAIN=$ZHIYAN_DOMAIN" >> "$ENVFILE"
  # 生成 Caddyfile
  cat > Caddyfile <<EOF
# 由 install.sh 生成 —— Caddy 自动 ACME（Let's Encrypt）HTTPS
$ZHIYAN_DOMAIN {
    reverse_proxy studio:80
}
EOF
  ok "已生成 Caddyfile（域名 $ZHIYAN_DOMAIN）"
fi
ok "$ENVFILE 已写入"

# ---------- 启动 ----------
COMPOSE_FILES="-f docker-compose.prod.yml"
if [ "$WITH_TLS" -eq 1 ]; then
  COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.tls.yml"
fi

info "拉取 / 构建镜像并启动（首次较慢）..."
docker compose $COMPOSE_FILES up -d --build

# ---------- 输出 ----------
echo
ok "部署完成 ✅"
echo
echo "  ┌──────────────────────────────────────────────────────────────┐"
echo "  │  访问地址：${C_BLU}$( [ "$WITH_TLS" -eq 1 ] && echo "https://$ZHIYAN_DOMAIN" || echo "http://<本机IP>:3006" )${C_RST}"
echo "  │  管理员账号：admin"
echo "  │  管理员密码：${C_YLW}$ZHIYAN_ADMIN_PASSWORD${C_RST}"
echo "  └──────────────────────────────────────────────────────────────┘"
echo
warn "请妥善保存管理员密码；首次登录后建议在「用户管理」中修改。"
if [ "$WITH_TLS" -eq 0 ]; then
  warn "当前为 HTTP（无 TLS）。生产环境建议配置反向代理 + 证书（./install.sh --with-tls）。"
fi
echo "  查看日志：docker compose $COMPOSE_FILES logs -f runtime"
echo "  停止服务：docker compose $COMPOSE_FILES down"
