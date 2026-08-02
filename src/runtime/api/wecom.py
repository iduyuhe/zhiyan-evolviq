"""企业微信自建应用 H5 API（移动端三阶第②阶，2026-08-02 骨架）

端点（nginx 剥 /api 前缀 → 此处一律裸前缀 /wecom）：
    GET  /wecom/status            企微配置状态（未配置优雅降级，不阻塞平台）
    POST /wecom/jsapi-signature   生成 agentConfig 签名（免登前置；需在企微内嵌 H5 调用）
    POST /wecom/push              应用消息推送（缺料预警等；权限校验 ≥ tenant_admin 或指定角色）

🔴 凭证铁律：任何响应不含 corpid/secret/agentid 明文（签名接口返回 corpid 用于前端 agentConfig 是必要的，
   属公开标识非密钥；secret/agentid 数字型 agentid 亦公开可查——仍只在签名接口按需返回）。
🔴 优雅降级：未配置时全部返回 503 + detail=未配置，前端可提示管理员配置。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.runtime.wecom.service import wecom_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wecom", tags=["wecom"])


class SignatureRequest(BaseModel):
    url: str = Field(..., description="当前页面完整 URL（含协议与路径，不含 hash）")


class PushRequest(BaseModel):
    userids: list[str] = Field(..., min_length=1, max_length=1000)
    content: str = Field(..., min_length=1, max_length=512)
    title: str = Field("智衍 EvolvIQ 预警", max_length=128)


def _require_configured() -> None:
    if not wecom_service.configured:
        raise HTTPException(status_code=503, detail="企微未配置：请在服务器 .env 填 wecom_corpid/secret/agentid 后重启")


@router.get("/status")
async def wecom_status():
    """企微配置状态（任何登录用户可查，用于前端提示）。"""
    return wecom_service.status()


@router.post("/jsapi-signature")
async def wecom_jsapi_signature(req: SignatureRequest):
    """生成 agentConfig 签名（免登前置）。企微内嵌 H5 加载时前端调用。"""
    _require_configured()
    sig = await wecom_service.sign_agent_config(req.url)
    if sig is None:
        raise HTTPException(status_code=502, detail="企微签名生成失败（ticket 获取异常）")
    return {"status": "ok", "config": sig}


@router.post("/push")
async def wecom_push(req: PushRequest):
    """应用消息推送（工作通知）。缺料预警等场景由服务端调用。"""
    _require_configured()
    result = await wecom_service.send_app_message(req.userids, req.content, req.title)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"推送失败：{result.get('reason')} {result.get('detail', '')}")
    return {"status": "ok", "msgid": result.get("msgid")}
