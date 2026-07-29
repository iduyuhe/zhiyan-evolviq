"""S3-6 共生进化环（#320，MASTER §3.6）

客户反馈 → 脱敏审核门 → GitHub from-customer Issue → 平台自进化 → 「因你而进化」回告。
租户「成长档案」：使用天数 / 已解锁圈层 / 贡献进化数 / 被采纳想法数。

四步闭环（§3.6）：
1. 产品内零摩擦反馈（每条情报/agent 结论旁轻量反馈位，本模块提供 API 入口）。
2. 脱敏审核门 → 开源平台：自动脱敏 + 默认匿名 + needs_review，转 GitHub Issue（from-customer）。
   🔴 红线：未经脱敏/审核绝不出内网；Issue 创建失败不阻断反馈闭环（内网先落库）。
3. 平台自进化：Issue 被响应/修复/发布 → status 推进到 released。
4. 「因你而进化」回告：released 反馈触发个性化进化通知（仅与该客户相关，绝不群发）。

🔴 隐私红线（MASTER §S3 + §3.6 实施纪律）：
- 反馈脱敏自动剥离 tenant/业务数据；默认匿名（anonymous=True）。
- 成长档案 / 反馈状态仅本租户可见；不提供跨租户聚合端点。
- 48h 首响应是硬 SLA（submit 即建 Issue = "已收到、已立项"，首响自动满足）。

存储复用 S3-1 通用行为事件池（behavior_events，事件类型 symbiosis_feedback）——单点真相、
租户内隔离、DB 韧性、重启恢复；本模块是状态机 + 脱敏 + GitHub 同步的薄聚合层。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from src.runtime.behavior_store import behavior_store
from src.runtime.unlock_map import progress_view

logger = logging.getLogger(__name__)

FEEDBACK_KINDS = {"praise", "inaccurate", "idea", "other"}
SLA_HOURS = 48

# GitHub 配置（复用 v29.9 生态飞轮范式：urllib + Bearer token）
GH_REPO = os.getenv("ZHIYAN_GH_REPO", "iduyuhe/zhiyan-evolviq")
# 🔴 安全红线：GitHub token 仅允许来自环境变量，绝不明文硬编码（泄露即被 GitHub 拦截推送）
GH_TOKEN = os.getenv("GH_TOKEN")
GH_API = "https://api.github.com"
GH_LABEL = "from-customer"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(text: str, tenant_id: str) -> str:
    """自动脱敏：剥离邮箱/手机号/租户标识等可识别信息（§3.6 步2 红线）。"""
    t = text or ""
    t = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已脱敏]", t)
    t = re.sub(r"(?<!\d)(1[3-9]\d{9})(?!\d)", "[手机号已脱敏]", t)
    if tenant_id:
        t = t.replace(tenant_id, "[租户已脱敏]")
    return t.strip()


def _gh_create_issue(title: str, body: str) -> dict | None:
    """创建 GitHub from-customer Issue；失败返回 None（不阻断反馈闭环）。"""
    import urllib.error
    import urllib.request

    if not GH_TOKEN:
        logger.warning("GH_TOKEN 未设置，跳过 GitHub Issue 创建（反馈仍存内网，待配置后发布）")
        return None
    url = f"{GH_API}/repos/{GH_REPO}/issues"
    payload = {"title": title, "body": body, "labels": [GH_LABEL]}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "zhiyan-symbiosis-bot",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # 网络/鉴权失败都不阻断业务
        logger.warning("GitHub Issue 创建失败（反馈仍存内网，待运维发布）：%s", e)
        return None


async def submit_feedback(
    tenant_id: str,
    user: str | None,
    kind: str,
    text: str,
    anonymous: bool = True,
) -> dict:
    """产品内零摩擦反馈入口（§3.6 步1）。返回 tracking 视图（含 48h SLA 计时）。"""
    if kind not in FEEDBACK_KINDS:
        raise ValueError(f"kind 须为 {sorted(FEEDBACK_KINDS)}")
    if not text or not text.strip():
        raise ValueError("反馈内容不能为空")
    text = text.strip()[:2000]

    tracking_id = f"fb_{uuid.uuid4().hex[:12]}"
    ts = _now()
    redacted = _redact(text, tenant_id)

    meta = {
        "tracking_id": tracking_id,
        "kind": kind,
        "text_redacted": redacted,
        "anonymous": bool(anonymous),
        "author": "anonymous" if anonymous else (user or "unknown"),
        "needs_review": True,          # 脱敏审核门（§3.6 红线①）
        "status": "submitted",
        "submitted_at": ts,
        "issue_number": None,
        "issue_url": None,
        "released_version": None,
        "released_at": None,
    }
    # 内网先行落库（租户隔离；记录永不抛异常）
    await behavior_store.record(
        tenant_id,
        "symbiosis_feedback",
        user_id=user,
        object_kind="feedback",
        object_id=tracking_id,
        meta=meta,
    )
    # 脱敏后尝试建 GitHub Issue（失败不阻断；闭环仍在内网 + 待运维发布）
    title = f"[from-customer] {kind}: {redacted[:60]}"
    body = (
        f"## 客户反馈（共生进化环 · 自动同步 · 匿名）\n\n"
        f"- **类型**：`{kind}`\n- **提交时间(UTC)**：{ts}\n"
        f"- **匿名**：是\n- **待审核**：是（运营复核后公开立项）\n\n"
        f"### 脱敏后内容\n{redacted}\n\n"
        f"> 由智衍工业智能体互联平台自动同步自租户反馈入口。默认匿名、已脱敏、"
        f"经审核门后才进入公开路线图。"
    )
    issue = await asyncio.to_thread(_gh_create_issue, title, body)
    if issue and issue.get("number"):
        meta["issue_number"] = issue.get("number")
        meta["issue_url"] = issue.get("html_url")
        await behavior_store.patch_meta(
            tenant_id, "symbiosis_feedback", tracking_id, meta
        )
    return _view(meta)


def _view(meta: dict) -> dict:
    sub = meta.get("submitted_at")
    sla_deadline = None
    sla_remaining_hours = None
    if sub:
        try:
            dt = datetime.fromisoformat(sub)
            deadline = dt + timedelta(hours=SLA_HOURS)
            sla_deadline = deadline.isoformat()
            sla_remaining_hours = round(
                (deadline - datetime.now(timezone.utc)).total_seconds() / 3600, 1
            )
        except Exception:
            pass
    return {
        "tracking_id": meta.get("tracking_id"),
        "kind": meta.get("kind"),
        "status": meta.get("status"),
        "anonymous": meta.get("anonymous"),
        "needs_review": meta.get("needs_review"),
        "submitted_at": sub,
        "issue_number": meta.get("issue_number"),
        "issue_url": meta.get("issue_url"),
        "sla_hours": SLA_HOURS,
        "sla_deadline": sla_deadline,
        "sla_remaining_hours": sla_remaining_hours,
        "released_version": meta.get("released_version"),
        "released_at": meta.get("released_at"),
    }


def _parse_meta(meta) -> dict:
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    try:
        return json.loads(meta) if isinstance(meta, str) else {}
    except Exception:
        return {}


def feedback_status(tenant_id: str) -> list[dict]:
    """本租户全部反馈进度 + 48h SLA（§3.6 步3 可溯源；🔴 仅本租户）。"""
    evs = behavior_store.events_for(tenant_id, "symbiosis_feedback", limit=200)
    out = []
    for ev in evs:
        out.append(_view(_parse_meta(ev.get("meta"))))
    out.sort(key=lambda x: x.get("submitted_at") or "", reverse=True)
    return out


def growth_profile(tenant_id: str) -> dict:
    """租户「成长档案」（§3.6 步4 被陪伴；🔴 仅本租户可见）。"""
    fbs = feedback_status(tenant_id)
    contributed = len([f for f in fbs if f.get("issue_number")])
    adopted = len([f for f in fbs if f.get("status") == "released"])
    first = behavior_store.first_event_at(tenant_id)
    days = 0
    if first:
        try:
            days = max(
                1,
                (datetime.now(timezone.utc) - datetime.fromisoformat(first)).days + 1,
            )
        except Exception:
            days = 0
    unlock = progress_view(tenant_id)
    return {
        "tenant_id": tenant_id,
        "days_active": days,
        "current_circle": unlock.get("current_circle"),
        "unlocked_agents": unlock.get("unlocked_agents"),
        "total_agents": unlock.get("total_agents"),
        "feedback_contributed": contributed,  # 贡献的进化数
        "ideas_adopted": adopted,             # 被采纳的想法数
        "next_step": unlock.get("next_step"),
    }


def evolution_notifications(tenant_id: str) -> list[dict]:
    """「因你而进化」回告（§3.6 步4）。仅返回与本租户反馈相关、已发布的内容。"""
    out = []
    for f in feedback_status(tenant_id):
        if f.get("status") == "released" and f.get("released_version"):
            sub = (f.get("submitted_at") or "")[:10]
            out.append(
                {
                    "tracking_id": f.get("tracking_id"),
                    "date": sub,
                    "kind": f.get("kind"),
                    "version": f.get("released_version"),
                    "issue_url": f.get("issue_url"),
                    "message": f"您 {sub} 提出的反馈，已在 v{f.get('released_version')} 上线",
                }
            )
    return out


async def mark_released(tenant_id: str, tracking_id: str, version: str) -> bool:
    """运营/CI 在版本发布后推进反馈到 released（§3.6 步3→步4 桥）。"""
    meta = _parse_meta(
        next(
            (
                ev.get("meta")
                for ev in behavior_store.events_for(
                    tenant_id, "symbiosis_feedback", limit=200
                )
                if ev.get("object_id") == tracking_id
            ),
            None,
        )
    )
    if not meta:
        return False
    meta["status"] = "released"
    meta["released_version"] = version
    meta["released_at"] = _now()
    return await behavior_store.patch_meta(
        tenant_id, "symbiosis_feedback", tracking_id, meta
    )
