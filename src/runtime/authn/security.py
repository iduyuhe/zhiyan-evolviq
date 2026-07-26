"""安全基元——密码哈希 + 无外部依赖的 JWT(HS256)

设计取舍（呼应「事实锚点 / 韧性降级」铁律）：
1. 不引入额外第三方依赖（passlib / pyjwt），用标准库 hashlib + hmac 实现，
   避免 pyproject 依赖膨胀与受管 venv 损坏风险。
2. 密码哈希用 PBKDF2-HMAC-SHA256（salt 随机、迭代 10 万次），格式
   `pbkdf2_sha256$<rounds>$<salt_hex>$<hash_hex>`，可平滑升级参数。
3. JWT 用 HS256：header.payload.signature，base64url(无填充)。
   签名密钥取自 ZHIYAN_JWT_SECRET，未配置则进程内随机生成（仅开发期，生产必须配置）。
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

# ---- JWT 密钥（进程级单例，lifespan 前可经 env 覆盖）----
JWT_SECRET = os.getenv("ZHIYAN_JWT_SECRET") or os.getenv("JWT_SECRET") or secrets.token_hex(32)
if not (os.getenv("ZHIYAN_JWT_SECRET") or os.getenv("JWT_SECRET")):
    # 开发期随机密钥：同一进程内 sign/verify 一致；重启即失效，生产必须配置固定密钥
    import logging

    logging.getLogger("zhiyan.authn").warning(
        "⚠️ 未配置 ZHIYAN_JWT_SECRET，使用进程随机密钥（重启即失效）；生产部署请在 .env 固定。"
    )

JWT_EXPIRE_SECONDS = int(os.getenv("ZHIYAN_JWT_EXPIRE", "86400"))  # 默认 24h
JWT_ISSUER = "zhiyan-evolviq"
JWT_ALG = "HS256"


# ---------------- 密码哈希 ----------------

_PBKDF2_ROUNDS = 100_000


def hash_password(password: str) -> str:
    """返回 `pbkdf2_sha256$rounds$salt$hash` 形式的存储串。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """恒定时间比较，避免时序攻击。"""
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds_s))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------------- JWT ----------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(segment: str) -> str:
    sig = hmac.new(JWT_SECRET.encode("utf-8"), segment.encode("utf-8"), hashlib.sha256).digest()
    return _b64url(sig)


def encode_jwt(payload: dict[str, Any], expire_seconds: int | None = None) -> str:
    """签发 JWT。payload 会被注入 iat / exp / iss。"""
    now = int(time.time())
    exp = now + (expire_seconds if expire_seconds is not None else JWT_EXPIRE_SECONDS)
    body = {**payload, "iat": now, "exp": exp, "iss": JWT_ISSUER}
    header = {"alg": JWT_ALG, "typ": "JWT"}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    seg = f"{h}.{p}"
    return f"{seg}.{_sign(seg)}"


def decode_jwt(token: str) -> dict[str, Any]:
    """校验签名 + 有效期，返回 payload；失败抛 ValueError。"""
    try:
        h, p, sig = token.split(".")
    except ValueError:
        raise ValueError("JWT 格式错误")
    if not hmac.compare_digest(_sign(f"{h}.{p}"), sig):
        raise ValueError("JWT 签名无效")
    try:
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
    except Exception:
        raise ValueError("JWT payload 解析失败")
    if payload.get("iss") != JWT_ISSUER:
        raise ValueError("JWT 签发方不匹配")
    exp = payload.get("exp")
    if exp is not None and int(time.time()) > int(exp):
        raise ValueError("JWT 已过期")
    return payload
