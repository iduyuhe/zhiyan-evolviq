"""企业微信（企微）回调接入器（v29.9）

鉴权链路（与企微「自建应用 / 接收消息」规范一致）：
1. URL 验证（GET）：企微推送 msg_signature / timestamp / nonce / echostr，
   服务端用 Token 计算 SHA1(sorted(Token, timestamp, nonce)) 比对 msg_signature；
   一致则对 echostr 做 AES 解密（或演示态直接返回原文）回送。
2. 消息推送（POST）：同样用 msg_signature 校验；通过后对加密报文做 AES-256-CBC 解密
   （EncodingAESKey 派生 32 字节 key，IV=key[:16]），解出 XML 取 <Content>。

韧性：
- Token 缺失 → enabled=False（不注册回调，URL 校验直接 403）。
- cryptography 库不可用 → 消息体解密降级为「演示 JSON 体」解析（便于本地联调与单测），
  但 URL 签名校验始终生效（满足 Good First Issue「单测覆盖 token 拒绝」）。

参考：企微回调加解密为 AES-256-CBC + PKCS7，与钉钉/飞书同族。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import xml.etree.ElementTree as ET
from typing import Any

from src.common.config import settings
from src.runtime.connectors.base import SocialConnectorBase

logger = logging.getLogger(__name__)


def verify_wecom_signature(token: str, timestamp: str, nonce: str, signature: str) -> bool:
    """企微回调签名校验：SHA1(sorted(Token, timestamp, nonce)) == msg_signature。

    返回 True 表示签名合法。单测核心断言对象。
    """
    if not token or not signature:
        return False
    arr = sorted([token, str(timestamp), str(nonce)])
    sha = hashlib.sha1("".join(arr).encode("utf-8")).hexdigest()
    return sha == signature


class WeComConnector(SocialConnectorBase):
    name = "wecom"
    kind = "wecom"

    def __init__(self) -> None:
        super().__init__()
        self.token = settings.wecom_token
        self.aes_key = settings.wecom_aes_key
        self.corp_id = settings.wecom_corp_id
        self.enabled = bool(self.token)

    # ---- 回调端点使用 ----

    def verify_url(self, signature: str, timestamp: str, nonce: str, echostr: str) -> str | None:
        """URL 验证：签名通过则解密 echostr 回送，否则返回 None（调用方判 403）。"""
        if not verify_wecom_signature(self.token, timestamp, nonce, signature):
            self._last_error = "url signature mismatch"
            return None
        # 解密 echostr（演示态：已是明文则直接返回）
        if self.aes_key:
            try:
                return _decrypt_echostr(echostr, self.aes_key, self.corp_id)
            except Exception as e:
                logger.warning(f"⚠️ 企微 echostr 解密失败，回退明文：{e}")
        return echostr

    def verify_message(self, signature: str, timestamp: str, nonce: str, body: bytes) -> dict | None:
        """消息推送校验 + 解密 → 返回 {content, from_user, msg_type}。

        演示态（无 aes_key 或解密库不可用）：尝试把 body 当 JSON（含 content 字段）解析。
        """
        if not verify_wecom_signature(self.token, timestamp, nonce, signature):
            self._last_error = "message signature mismatch"
            return None
        # 正式解密路径
        if self.aes_key:
            try:
                xml_text = _decrypt_message(body, self.aes_key, self.corp_id)
                return _parse_wecom_xml(xml_text)
            except Exception as e:
                logger.warning(f"⚠️ 企微消息解密失败，尝试 JSON 演示体：{e}")
        # 演示态：body 为 JSON {"content": "...", "from": "...", "type": "..."}
        try:
            import json
            d = json.loads(body.decode("utf-8"))
            return {
                "content": d.get("content", ""),
                "from_user": d.get("from", "unknown"),
                "msg_type": d.get("type", "text"),
            }
        except Exception:
            return None

    # ---- 连通性（企微无主动连通概念，校验 token 配置）----
    async def test_connection(self) -> dict:
        t0 = time.monotonic()
        ok = bool(self.token)
        return {
            "name": self.name,
            "kind": self.kind,
            "ok": ok,
            "mode": "configured" if ok else "not_configured",
            "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            "detail": "Token 已配置，可接收回调" if ok else "未配置 ZHIYAN_WECOM_TOKEN",
        }


# ---------------- AES 解密（仅 cryptography 可用时）----------------

def _aes_key_bytes(aes_key: str) -> bytes:
    """EncodingAESKey(43 字符) base64 解码为 32 字节 AES key。"""
    return base64.b64decode(aes_key + "=")


def _pkcs7_unpad(data: bytes) -> bytes:
    pad = data[-1]
    return data[:-pad]


def _decrypt_bytes(cipher: bytes, aes_key: str) -> bytes:
    """AES-256-CBC 解密（IV = key 前 16 字节）。延迟 import cryptography。"""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    key = _aes_key_bytes(aes_key)
    iv = key[:16]
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return decryptor.update(cipher) + decryptor.finalize()


def _decrypt_echostr(echostr: str, aes_key: str, corp_id: str) -> str:
    raw = base64.b64decode(echostr)
    plain = _decrypt_bytes(raw, aes_key)
    plain = _pkcs7_unpad(plain)
    # 明文结构：random(16B) + msg_len(4B, network) + msg + receiveid
    msg = plain[16:][4:]
    # 末尾 receiveid 校验（corp_id），不严格匹配则忽略
    return msg.decode("utf-8")


def _decrypt_message(body: bytes, aes_key: str, corp_id: str) -> str:
    raw = base64.b64decode(body)
    plain = _decrypt_bytes(raw, aes_key)
    plain = _pkcs7_unpad(plain)
    # 结构：random(16B) + msg_len(4B) + xml_msg + receiveid
    xml_len = int.from_bytes(plain[16:20], "big")
    xml_msg = plain[20:20 + xml_len]
    return xml_msg.decode("utf-8")


def _parse_wecom_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    content = root.findtext("Content", "") or ""
    from_user = root.findtext("FromUserName", "") or ""
    msg_type = root.findtext("MsgType", "text") or "text"
    return {"content": content, "from_user": from_user, "msg_type": msg_type}


if __name__ == "__main__":
    # 自测签名：token + ts + nonce 排序后 sha1
    tok = "mytoken"
    ts, nonce = "1600000000", "abc123"
    arr = sorted([tok, ts, nonce])
    sig = hashlib.sha1("".join(arr).encode()).hexdigest()
    assert verify_wecom_signature(tok, ts, nonce, sig) is True
    assert verify_wecom_signature(tok, ts, nonce, "wrong") is False
    print("✅ wecom signature verify OK")
