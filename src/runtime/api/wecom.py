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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.runtime.wecom.service import wecom_service
from src.runtime.api.deps import get_tenant

logger = logging.getLogger(__name__)

# 鉴权路由（JWT 保护）
router = APIRouter(prefix="/wecom", tags=["wecom"])
# 公开路由（企微 OAuth 回跳，平台无法带 token）——仅 /bind/confirm，靠签名/OAuth 鉴权
public_router = APIRouter(prefix="/wecom", tags=["wecom-public"])


class SignatureRequest(BaseModel):
    url: str = Field(..., description="当前页面完整 URL（含协议与路径，不含 hash）")


class PushRequest(BaseModel):
    userids: list[str] = Field(..., min_length=1, max_length=1000)
    content: str = Field(..., min_length=1, max_length=512)
    title: str = Field("智衍 EvolvIQ 预警", max_length=128)


class BindRequest(BaseModel):
    """Web 端发起「生成绑定二维码」：对当前登录租户建一次性绑定令牌。"""
    pass


class PushApprovalRequest(BaseModel):
    session_id: str = Field(..., description="待审批会话 ID")
    summary: str = Field("", description="推送给审批人的决策摘要（出站会脱敏）")
    title: str = Field("待您终审的决策", max_length=40)
    approver_userid: str | None = Field(None, description="指定审批人 userid（缺省取绑定表首位）")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=512, description="移动端「问分身」问题")


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


# ============ 扫码即联（IM 对接 Phase）============

@router.post("/bind")
async def create_bind(_req: BindRequest, tenant: str = Depends(get_tenant)):
    """生成「绑定二维码」载荷：对当前租户建一次性绑定令牌（扫码即联）。"""
    from src.common.config import settings
    from src.runtime.wecom.binding import binding_store

    s = binding_store.create_bind_session(tenant)
    payload = binding_store.build_qr_payload(s.token, corp_id_hint=settings.wecom_corp_id or None)
    return {
        "status": "ok",
        "tenant": tenant,
        "token": payload["token"],
        "confirm_url": payload["confirm_url"],  # 二维码文本
        "ttl": payload["ttl"],
        "corp_id_hint": payload["corp_id_hint"],
    }


@public_router.get("/bind/confirm")
async def confirm_bind(
    token: str = Query(..., description="绑定令牌"),
    code: str = Query("", description="企微 OAuth code（snsapi_base）"),
    userid: str = Query("", description="演示态无 OAuth 时的 userid 兜底"),
    corp: str = Query("", description="corp_id 提示（OAuth 回跳时带入）"),
):
    """扫码即联确认页（公开，企微 OAuth 回跳）。

    1. 用 OAuth code 换 userid（生产）；演示态允许 userid 兜底。
    2. corp_id 取本平台配置（即本企微企业）；confirm_bind 落库映射。
    🔴 不返回任何凭证；失败仅回 reason。
    """
    from src.common.config import settings
    from src.runtime.wecom.binding import binding_store

    uid = None
    if code:
        uid = await wecom_service.get_userid_by_oauth_code(code)
    if not uid and userid:
        uid = userid
    if not uid:
        return {"ok": False, "reason": "cannot_resolve_userid"}
    corp_id = settings.wecom_corp_id or corp
    if not corp_id:
        return {"ok": False, "reason": "corp_unknown"}
    result = binding_store.confirm_bind(token, corp_id, uid)
    return result


@router.post("/push-approval")
async def push_approval(req: PushApprovalRequest, tenant: str = Depends(get_tenant)):
    """主动推送审批卡片给绑定审批人（后端创建待审会话后调用）。"""
    _require_configured()
    from src.runtime.wecom.im_bridge import push_approval_card

    r = await push_approval_card(req.session_id, tenant, req.summary, title=req.title, approver_userid=req.approver_userid)
    if not r.get("ok"):
        raise HTTPException(status_code=502, detail=f"审批卡片推送失败：{r.get('reason')}")
    return {"status": "ok", "approver": r.get("approver"), "push": r.get("push")}


@router.post("/query")
async def wecom_query(req: QueryRequest, tenant: str = Depends(get_tenant)):
    """移动端「问分身」Web 触发入口（只读 L0–L2）。真实入口在企微回调，此处便于联调。"""
    _require_configured()
    from src.runtime.wecom.im_bridge import handle_text_query

    r = await handle_text_query(req.question, userid=None, tenant=tenant)
    return {"status": "ok" if r.get("ok") else "error", **r}
