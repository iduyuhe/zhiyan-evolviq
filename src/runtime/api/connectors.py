"""社交通道接入 API（v29.9）

端点（受全局 JWT 门禁）：
    GET  /api/connectors                 列出已配置社交连接器 + 状态
    GET  /api/connectors/{name}/test     连通性 / token 校验测试
    GET  /api/connectors/wecom/callback  企微 URL 验证（msg_signature/timestamp/nonce/echostr）
    POST /api/connectors/wecom/callback  企微消息推送（签名校验 + 解密 → UNS social）
    POST /api/connectors/dingtalk/callback 钉钉消息推送（加签校验 → UNS social）
    POST /api/connectors/email/pull      手动触发邮件拉取

回调端点对外部平台开放：仅 wecom/dingtalk 回调**免 JWT**（平台无法带 token）；
其余管理端点走全局门禁。实现上本 router 不挂 _AUTH_DEPS，单独在 wecom/dingtalk 回调内
做 token 校验（这才是真正的鉴权），管理端点通过依赖注入鉴权。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, HTTPException, Depends

from src.runtime.connectors.manager import manager
from src.runtime.authn.deps import require_auth

logger = logging.getLogger(__name__)

# 回调端点（企微/钉钉平台调用，免 JWT）—— 真实鉴权在 token/签名校验内
callback_router = APIRouter(prefix="/connectors", tags=["connectors-callback"])
# 管理端点（需 JWT）
admin_router = APIRouter(prefix="/connectors", tags=["connectors"], dependencies=[Depends(require_auth)])


# ============ 管理端点（需 JWT）============

@admin_router.get("")
async def list_connectors():
    return {"connectors": manager.list()}


@admin_router.get("/{name}/test")
async def test_connector(name: str):
    return await manager.test(name)


@admin_router.post("/email/pull")
async def pull_email(limit: int = 20):
    return await manager.pull_email(limit=limit)


# ============ 企微回调（免 JWT，靠签名鉴权）============

@callback_router.get("/wecom/callback")
async def wecom_url_verify(
    msg_signature: str = "", timestamp: str = "", nonce: str = "", echostr: str = ""
):
    c = manager.get("wecom")
    if c is None or not c.enabled:
        raise HTTPException(status_code=403, detail="企微连接器未启用")
    result = c.verify_url(msg_signature, timestamp, nonce, echostr)
    if result is None:
        raise HTTPException(status_code=403, detail="签名校验失败")
    return result  # 明文 echostr 回送（纯文本）


@callback_router.post("/wecom/callback")
async def wecom_message(request: Request, msg_signature: str = "", timestamp: str = "", nonce: str = ""):
    c = manager.get("wecom")
    if c is None or not c.enabled:
        raise HTTPException(status_code=403, detail="企微连接器未启用")
    body = await request.body()
    parsed = c.verify_message(msg_signature, timestamp, nonce, body)
    if parsed is None:
        raise HTTPException(status_code=403, detail="签名/解密校验失败")
    evt_id = c.publish(
        text=parsed["content"],
        entities=[f"wecom:{parsed['from_user']}"],
        source=f"wecom://app",
        confidence=1.0,
    )
    return {"status": "captured", "event_id": evt_id, "from": parsed["from_user"]}


# ============ 钉钉回调（免 JWT，靠加签鉴权）============

@callback_router.post("/dingtalk/callback")
async def dingtalk_message(request: Request, timestamp: str = "", sign: str = ""):
    c = manager.get("dingtalk")
    if c is None or not c.enabled:
        raise HTTPException(status_code=403, detail="钉钉连接器未启用")
    body = await request.body()
    parsed = c.verify_and_parse(timestamp, sign, body)
    if parsed is None:
        raise HTTPException(status_code=403, detail="加签校验失败")
    evt_id = c.publish(
        text=parsed["content"],
        entities=[f"dingtalk:{parsed['sender']}"],
        source=f"dingtalk://robot",
        confidence=1.0,
    )
    return {"status": "captured", "event_id": evt_id, "sender": parsed["sender"]}
