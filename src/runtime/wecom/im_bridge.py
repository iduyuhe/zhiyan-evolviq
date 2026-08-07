"""IM 桥接（企微 ↔ 智衍 EvolvIQ 人机协同，2026-08-03）

定位：把「企微消息/按钮回调」翻译成「平台决策动作」，是移动端审核 + 查询的枢纽。

入站路由（handle_inbound）：
- 文本消息 → handle_text_query（只读 L0–L2：规划预览，绝不 execute，零副作用）
- 审批按钮回调（EventKey=APPROVE/REJECT:<session_id>）→ process_approval（人留终审，调 engine.execute/reject）

出站铁律：
- 🔴 所有出站文本经 sanitize_im_text 零真名脱敏（绝不外发研究案例真实锚定名）。
- 🔴 租户归属 fail-closed：审批前校验 session.tenant_id == 绑定解析出的 tenant，跨租户一律拒绝。
- 优雅降级：企微未配置 / 无绑定审批人 → 返回明确 reason，绝不抛异常破管。

依赖：复用 sessions API 的 engine 单例（保证审批作用于真实会话），
      binding_store（租户↔corp↔userid），wecom_service（卡片推送）。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def sanitize_im_text(text: str) -> str:
    """出站零真名脱敏（🔴 铁律）：任何推给企微的文本都先过此关。"""
    from src.common.leak import sanitize_leak

    return sanitize_leak(text or "")


def _resolve_tenant(parsed: dict, corp_id: str | None = None) -> str | None:
    """从入站消息解析租户（fail-closed：无任何绑定记录则 None）。"""
    from src.runtime.wecom.binding import binding_store

    # 优先 corp_id（回调连接器持有），其次 userid
    tenant = binding_store.resolve_tenant_by_corp(corp_id)
    if tenant:
        return tenant
    return binding_store.resolve_tenant_by_user(parsed.get("from_user"))


async def handle_inbound(parsed: dict, corp_id: str | None = None) -> dict:
    """统一入站入口：企微回调（文本 / 审批按钮）都先到这。

    Args:
        parsed: wecom_ingest.verify_message 的结果
                {content, from_user, msg_type, event, event_key, task_id}
        corp_id: 企微 corp_id（连接器持有，用于租户解析）
    Returns:
        {"ok": bool, ...} 调用方据此回 200（企微要求 2s 内回执）。
    """
    if not parsed:
        return {"ok": False, "reason": "empty_parsed"}

    tenant = _resolve_tenant(parsed, corp_id)
    if not tenant:
        # 🔴 fail-closed：未绑定无法定位租户 → 不处理（避免误路由到 default）
        logger.warning("⚠️ [im_bridge] 入站消息无法解析租户（未绑定），已忽略")
        return {"ok": False, "reason": "tenant_unresolved_unbound"}

    # 1) 审批按钮回调
    event_key = parsed.get("event_key")
    from src.runtime.connectors.wecom_ingest import parse_approval_event_key

    approval = parse_approval_event_key(event_key)
    if approval:
        return await process_approval(
            session_id=approval["session_id"],
            action=approval["action"],
            userid=parsed.get("from_user"),
            tenant=tenant,
        )

    # 2) 文本消息 → 只读查询
    content = (parsed.get("content") or "").strip()
    if content:
        return await handle_text_query(content, parsed.get("from_user"), tenant)

    return {"ok": False, "reason": "no_routable_content"}


async def process_approval(session_id: str, action: str, userid: str | None, tenant: str) -> dict:
    """审批按钮 → 人留终审：执行 / 驳回真实会话。

    🔴 fail-closed：session.tenant_id 必须与绑定解析 tenant 完全一致，否则拒绝（防跨租户审批）。
    """
    from src.runtime.api.sessions import get_engine

    engine = get_engine()
    session = engine.get_session(session_id)
    if not session:
        logger.warning(f"⚠️ [im_bridge] 审批目标会话不存在：{session_id}")
        return {"ok": False, "reason": "session_not_found"}

    # 🔴 租户归属校验：跨租户审批一律拒绝
    if session.get("tenant_id") != tenant:
        logger.warning(
            f"⚠️ [im_bridge] 租户不匹配拒绝审批：session.tenant={session.get('tenant_id')} != 解析tenant={tenant}"
        )
        return {"ok": False, "reason": "tenant_mismatch"}

    try:
        if action == "approve":
            result = await engine.execute(session_id, tenant_id=tenant)
            verb = "已通过并执行"
        else:
            result = await engine.reject(session_id, feedback="企微移动端驳回", tenant_id=tenant)
            verb = "已驳回"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ [im_bridge] 审批执行异常：{e}")
        return {"ok": False, "reason": "engine_error", "detail": str(e)}

    # 出站零真名脱敏
    safe_summary = sanitize_im_text(_summarize_result(result))
    from src.runtime.wecom.service import wecom_service

    card = wecom_service.build_result_card(title=f"决策{verb}", content=safe_summary)
    push = await wecom_service.send_template_card([userid] if userid else [], card)
    return {"ok": True, "action": action, "session_id": session_id, "push": push}


async def handle_text_query(question: str, userid: str | None, tenant: str) -> dict:
    """移动端「问分身」——只读 L0–L2 规划预览，绝不 execute（零副作用）。

    锁死只读：只生成规划（agent 的计划 / 推理大纲），不触发任何执行动作，
    符合对外叙事「L0 观察 → L2 预案」的免费外圈定位；结果出站脱敏。
    """
    from src.runtime.api.sessions import get_engine

    engine = get_engine()
    session_id = str(uuid.uuid4())
    try:
        plan = await engine.plan(session_id, question, tenant_id=tenant)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ [im_bridge] 文本查询规划异常：{e}")
        return {"ok": False, "reason": "plan_error", "detail": str(e)}

    routed = engine.get_session(session_id).get("agent")
    # 规划预览即「只读答案」——出站脱敏
    safe_preview = sanitize_im_text((plan or "")[:800])
    from src.runtime.wecom.service import wecom_service

    card = wecom_service.build_result_card(
        title="分身解读（只读预览）",
        content=f"路由分身：{routed or '智能体'}\n\n{safe_preview}",
    )
    push = await wecom_service.send_template_card([userid] if userid else [], card)
    return {
        "ok": True,
        "session_id": session_id,
        "routed_agent": routed,
        "read_only": True,
        "push": push,
    }


async def push_approval_card(
    session_id: str,
    tenant: str,
    summary: str,
    title: str = "待您终审的决策",
    approver_userid: str | None = None,
) -> dict:
    """主动推送审批卡片给绑定审批人（后端创建待审会话后调用）。

    审批人解析：优先用传入 approver_userid，否则取绑定表中该租户首位审批人。
    """
    from src.runtime.wecom.binding import binding_store
    from src.runtime.wecom.service import wecom_service

    uid = approver_userid or binding_store.resolve_approver_userid(tenant)
    if not uid:
        return {"ok": False, "reason": "no_bound_approver"}
    # 🔴 卡片内容脱敏
    safe_summary = sanitize_im_text(summary or "")
    card = wecom_service.build_approval_card(session_id, title, safe_summary, tenant)
    push = await wecom_service.send_template_card([uid], card)
    return {"ok": push.get("ok", False), "approver": uid, "push": push}


def _summarize_result(result: Any) -> str:
    """把执行/驳回结果压成卡片可展示文本（脱敏在调用方完成）。"""
    if result is None:
        return "（无结果）"
    if isinstance(result, dict):
        # 优先取人类可读摘要字段
        for key in ("summary", "text", "message", "detail"):
            if result.get(key):
                return str(result[key])[:512]
        try:
            return json.dumps(result, ensure_ascii=False, default=str)[:512]
        except Exception:
            return str(result)[:512]
    return str(result)[:512]
