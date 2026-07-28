"""共生进化环——反馈 API（§3.6 S2 落点）

- POST /feedback：提交反馈（👍/👎/💡 + 可选文本/目标），租户隔离。
- GET  /feedback：我的反馈列表（本租户，按状态过滤）。
- GET  /feedback/board：48h 首响应 SLA 看板（租户管理员看本租户，超级管理员看全平台）。
- POST /feedback/{id}/escalate：脱敏审核门 → 提报 GitHub Issue（from-customer）。
- POST /feedback/{id}/reject：人工驳回（仅内部闭环，不出内网）。

红线：
- 所有反馈强租户隔离，跨租户不可见、不可操作（超级管理员仅平台级看板，不越权改他租户反馈）。
- escalate 前必过 desensitize()，未脱敏绝对不出内网。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.runtime.authn.deps import require_auth
from src.runtime.feedback_store import feedback_store
from src.runtime.tenant_store import tenant_store
from src.runtime.models.feedback import FB_LIKE

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    feedback_type: str  # like/dislike/idea
    text: str | None = None
    target_kind: str | None = None  # signal/agent_conclusion/other
    target_id: str | None = None


@router.post("")
async def submit_feedback(req: FeedbackRequest, u: dict = Depends(require_auth)):
    """提交反馈。租户取自 JWT（require_auth 已 set_current_tenant）。"""
    try:
        rec = await feedback_store.submit(
            tenant_id=u["tenant_id"],
            user_id=u.get("username"),
            feedback_type=req.feedback_type,
            target_kind=req.target_kind,
            target_id=req.target_id,
            text=req.text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "received", "feedback": rec}


@router.get("")
async def my_feedback(
    status: str | None = None,
    u: dict = Depends(require_auth),
):
    """我的反馈列表（本租户）。"""
    items = feedback_store.list_for(u["tenant_id"], status)
    return {"total": len(items), "feedbacks": items}


@router.get("/board")
async def feedback_board(u: dict = Depends(require_auth)):
    """48h 首响应 SLA 看板。

    - 超级管理员：全平台视图。
    - 租户管理员：仅本租户视图。
    - 其他角色：无权限。
    """
    role = u.get("role", "VIEWER")
    if role not in ("TENANT_ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="仅租户管理员/超级管理员可查看反馈看板")
    scope = None if role == "SUPERADMIN" else u["tenant_id"]
    return feedback_store.board_stats(scope)


@router.post("/{fb_id}/escalate")
async def escalate_feedback(fb_id: str, u: dict = Depends(require_auth)):
    """脱敏审核门：把反馈提报为 GitHub Issue（from-customer）。

    权限：超级管理员可提报任意反馈；租户管理员仅可提报本租户反馈。
    """
    fb = feedback_store.get(fb_id)
    if fb is None:
        raise HTTPException(status_code=404, detail="反馈不存在")
    role = u.get("role", "VIEWER")
    if role not in ("TENANT_ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="仅租户管理员/超级管理员可审核反馈")
    if role != "SUPERADMIN" and fb["tenant_id"] != u["tenant_id"]:
        raise HTTPException(status_code=403, detail="无权操作他租户的反馈")
    # 仅含文本的实质反馈才进开源（👍 类纯信号不提报）
    if fb["feedback_type"] == FB_LIKE and not fb.get("text"):
        raise HTTPException(status_code=400, detail="👍 类纯信号反馈无需提报开源")
    tenant = tenant_store.get(fb["tenant_id"])
    tenant_name = tenant.name if tenant else ""
    try:
        result = await feedback_store.escalate(fb_id, reviewer=u.get("username", "human"), tenant_name=tenant_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/{fb_id}/reject")
async def reject_feedback(fb_id: str, u: dict = Depends(require_auth)):
    """人工驳回（仅内部闭环，不出内网）。权限同 escalate。"""
    fb = feedback_store.get(fb_id)
    if fb is None:
        raise HTTPException(status_code=404, detail="反馈不存在")
    role = u.get("role", "VIEWER")
    if role not in ("TENANT_ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="仅租户管理员/超级管理员可审核反馈")
    if role != "SUPERADMIN" and fb["tenant_id"] != u["tenant_id"]:
        raise HTTPException(status_code=403, detail="无权操作他租户的反馈")
    try:
        result = await feedback_store.reject(fb_id, reviewer=u.get("username", "human"))
    except KeyError:
        raise HTTPException(status_code=404, detail="反馈不存在")
    return result
