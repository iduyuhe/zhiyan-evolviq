"""共生进化环——反馈存储 + 脱敏管道 + 48h SLA 看板（§3.6）

内存注册表 + 数据库持久化（与 env_subscription_store 同构，韧性降级）：
- db 可用：反馈落库（feedbacks 表），重启后恢复。
- db 不可用：仅内存持有，重启即失。

三大职责：
1. 提交 submit()：租户隔离落库，自动算 first_response_due_at（created_at+48h）。
2. 脱敏 desensitize()：剥离租户名 / 邮箱 / 手机 / 证件号 / 卡号——「脱敏审核门」第一关。
3. 提报 escalate()：脱敏后转 GitHub Issue（from-customer 标签），回链 + 写 responded_at。
4. 看板 board_stats()：48h SLA 度量（待响应/逾期/已闭环）。

红线：未经脱敏 + 审核的反馈绝不出内网；提报前必过 desensitize。
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.common import db
from src.runtime.github_client import create_issue
from src.runtime.models.feedback import (
    FB_DISLIKE,
    FB_IDEA,
    FB_ISSUED,
    FB_LIKE,
    FB_PENDING_REVIEW,
    FB_RECEIVED,
    FB_REJECTED,
    Feedback,
)

logger = logging.getLogger(__name__)

_SLA_HOURS = 48

# ---------- 自动脱敏（剥离租户名 / PII / 业务敏感字段） ----------
# 注意边界：(?<!\d) / (?!\d) 防止手机号子串误命中身份证/银行卡等长数字串。
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDCARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_BANK = re.compile(r"(?<!\d)\d{16,19}(?!\d)")


def _tenant_aliases(name: str) -> list[str]:
    """租户名及其去后缀核心（如「上海杜特企业管理咨询有限公司」→「上海杜特」），用于脱敏。"""
    aliases = {name}
    base = name
    for suf in ("企业管理咨询有限公司", "股份有限公司", "有限责任公司", "有限公司", "（集团）", "(集团)", "集团", "公司"):
        if base.endswith(suf) and len(base) > len(suf):
            base = base[: -len(suf)]
            aliases.add(base)
    # 长优先替换，避免短别名误命中长别名内部
    return sorted(aliases, key=len, reverse=True)


def desensitize(text: str | None, tenant_name: str = "") -> str:
    """自动脱敏：剥离租户名（含去后缀核心）+ 常见 PII。空文本返回空串。

    设计：仅做结构型脱敏（租户名替换、PII 掩码），不臆造、不留存原文。
    """
    if not text:
        return ""
    t = text
    if tenant_name:
        for alias in _tenant_aliases(tenant_name):
            if alias:
                t = t.replace(alias, "〔租户〕")
    t = _EMAIL.sub("〔邮箱〕", t)
    t = _PHONE.sub("〔手机〕", t)
    t = _IDCARD.sub("〔证件号〕", t)
    t = _BANK.sub("〔卡号〕", t)
    return t


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeedbackStore:
    """反馈注册表（进程级单例语义）"""

    def __init__(self) -> None:
        self._by_id: dict[str, Feedback] = {}

    # ---------- 生命周期 ----------
    async def init(self) -> None:
        """从库加载全部反馈到内存（main lifespan 在 init_db 之后调用；幂等）。"""
        if not db.db_available or db.async_session is None:
            logger.warning("⚠️ 反馈存储降级为内存态（db 不可用），重启即失")
            return
        try:
            async with db.async_session() as s:
                rows = (await s.execute(select(Feedback))).scalars().all()
                for r in rows:
                    self._by_id[r.id] = r
            logger.info(f"✅ 反馈加载：{len(self._by_id)} 条")
        except Exception as e:
            logger.warning(f"⚠️ 反馈加载失败，降级内存态：{e}")

    # ---------- 写入 ----------
    async def submit(
        self,
        tenant_id: str,
        user_id: str | None,
        feedback_type: str,
        target_kind: str | None,
        target_id: str | None,
        text: str | None,
    ) -> dict:
        """提交一条反馈。校验类型；自动算 48h SLA 截止。返回落库 dict。"""
        if feedback_type not in (FB_LIKE, FB_DISLIKE, FB_IDEA):
            raise ValueError(f"feedback_type 须为 {FB_LIKE}/{FB_DISLIKE}/{FB_IDEA} 之一")
        now = datetime.now(timezone.utc)
        due = (now + timedelta(hours=_SLA_HOURS)).isoformat()
        fb = Feedback(
            id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            user_id=user_id,
            feedback_type=feedback_type,
            target_kind=target_kind,
            target_id=target_id,
            text=text or None,
            status=FB_RECEIVED,
            first_response_due_at=due,
            created_at=now,
        )
        self._by_id[fb.id] = fb
        await self._persist(fb)
        logger.info(f"📨 收到反馈 {fb.id}（{feedback_type}，租户 {tenant_id}）")
        return fb.to_dict()

    async def _persist(self, fb: Feedback) -> None:
        if not (db.db_available and db.async_session is not None):
            return
        try:
            async with db.async_session() as s:
                obj = await s.get(Feedback, fb.id)
                if obj is None:
                    s.add(fb)
                else:
                    obj.tenant_id = fb.tenant_id
                    obj.user_id = fb.user_id
                    obj.feedback_type = fb.feedback_type
                    obj.target_kind = fb.target_kind
                    obj.target_id = fb.target_id
                    obj.text = fb.text
                    obj.status = fb.status
                    obj.desensitized_text = fb.desensitized_text
                    obj.github_issue_url = fb.github_issue_url
                    obj.github_issue_number = fb.github_issue_number
                    obj.reviewer = fb.reviewer
                    obj.first_response_due_at = fb.first_response_due_at
                    obj.responded_at = fb.responded_at
                await s.commit()
        except Exception as e:
            logger.warning(f"⚠️ 反馈持久化失败（内存已更新）：{e}")

    # ---------- 查询 ----------
    def get(self, fb_id: str) -> dict | None:
        fb = self._by_id.get(fb_id)
        return fb.to_dict(include_internal=True) if fb else None

    async def delete(self, fb_id: str) -> bool:
        """删除一条反馈（测试清理用；生产路径不暴露删除端点）。"""
        fb = self._by_id.pop(fb_id, None)
        if fb is None:
            return False
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    obj = await s.get(Feedback, fb_id)
                    if obj:
                        await s.delete(obj)
                        await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 反馈删除持久化失败（内存已移除）：{e}")
        return True

    def list_for(self, tenant_id: str, status: str | None = None) -> list[dict]:
        out = [
            fb.to_dict()
            for fb in self._by_id.values()
            if fb.tenant_id == tenant_id and (status is None or fb.status == status)
        ]
        out.sort(key=lambda d: d["created_at"] or "", reverse=True)
        return out

    def list_all(self) -> list[dict]:
        """平台级全量反馈读取（供自我进化环采集评估信号用，只读、不暴露 PII 原文）。"""
        return [fb.to_dict() for fb in self._by_id.values()]

    # ---------- 审核门：脱敏 → 提报开源 Issue ----------
    async def escalate(self, fb_id: str, reviewer: str, tenant_name: str = "") -> dict:
        """脱敏审核门：把反馈转为 GitHub Issue（from-customer），回链 + 写响应时刻。

        返回 {'success': bool, 'github_issue_url':..., 'github_issue_number':..., 'status':...}
        失败（GitHub 不可用/无文本）时反馈不伪造成功，状态保持 pending_review。
        """
        fb = self._by_id.get(fb_id)
        if fb is None:
            raise KeyError(fb_id)
        if not fb.text:
            raise ValueError("无文本内容的反馈无需提报（仅 👍 类信号不进开源 Issue）")
        # 第一关：自动脱敏（剥离租户名/PII）
        clean = desensitize(fb.text, tenant_name)
        fb.desensitized_text = clean
        fb.status = FB_PENDING_REVIEW
        # 第二关：人工审核（reviewer 由调用方鉴权保证）→ 提报开源
        title = f"[from-customer] {_type_label(fb.feedback_type)}：{clean[:40]}"
        body = (
            f"## 共生进化环 · 客户反馈（from-customer）\n\n"
            f"**类型**：{_type_label(fb.feedback_type)}\n"
            f"**提交时间（UTC）**：{fb.created_at.isoformat() if fb.created_at else '未知'}\n"
            f"**反馈 ID**：`{fb.id}`\n\n"
            f"### 反馈内容（已自动脱敏）\n\n{clean}\n\n"
            f"> 本条反馈经平台脱敏审核门处理后提报，原始租户信息与 PII 已剥离。\n"
            f"> 反馈 ↔ Issue ↔ 版本 三向溯源：客户可在平台内查看本条反馈的处理进度。"
        )
        issue = create_issue(title, body, labels=["from-customer"])
        if issue:
            fb.status = FB_ISSUED
            fb.github_issue_url = issue["url"]
            fb.github_issue_number = issue["number"]
            fb.responded_at = _now_iso()  # 首次回音（48h SLA 达成）
            logger.info(f"🚀 反馈 {fb.id} 已提报 GitHub Issue #{issue['number']}：{issue['url']}")
        else:
            # GitHub 不可用：保留 pending_review，待运营手动补提报
            logger.warning(f"⚠️ 反馈 {fb.id} 脱敏完成但未提报（GitHub 不可用），状态 pending_review")
        fb.reviewer = reviewer
        await self._persist(fb)
        return {
            "success": issue is not None,
            "status": fb.status,
            "github_issue_url": fb.github_issue_url,
            "github_issue_number": fb.github_issue_number,
            "desensitized_text": clean,
        }

    async def reject(self, fb_id: str, reviewer: str) -> dict:
        """人工驳回：仅内部闭环，不出内网。"""
        fb = self._by_id.get(fb_id)
        if fb is None:
            raise KeyError(fb_id)
        fb.status = FB_REJECTED
        fb.reviewer = reviewer
        fb.responded_at = _now_iso()
        await self._persist(fb)
        return fb.to_dict()

    # ---------- 48h SLA 看板 ----------
    def board_stats(self, tenant_id: str | None = None) -> dict:
        """48h 首响应 SLA 看板。tenant_id=None 表示平台级（全租户）。"""
        items = [fb for fb in self._by_id.values() if tenant_id is None or fb.tenant_id == tenant_id]
        counts: dict[str, int] = {}
        for fb in items:
            counts[fb.status] = counts.get(fb.status, 0) + 1
        now = datetime.now(timezone.utc)
        pending = [fb for fb in items if fb.status in (FB_RECEIVED, FB_PENDING_REVIEW)]
        overdue = [
            fb for fb in pending
            if fb.first_response_due_at and fb.first_response_due_at < now.isoformat()
        ]
        closed = [fb for fb in items if fb.status in (FB_ISSUED, FB_REJECTED)]
        responded_within = [
            fb for fb in closed
            if fb.responded_at and fb.first_response_due_at and fb.responded_at <= fb.first_response_due_at
        ]
        recent = sorted(items, key=lambda x: x.created_at.isoformat() if x.created_at else "", reverse=True)[:10]
        return {
            "scope": tenant_id or "platform",
            "total": len(items),
            "counts": counts,
            "pending": len(pending),
            "overdue": len(overdue),
            "closed": len(closed),
            "sla_met": len(responded_within),
            "sla_rate": round(len(responded_within) / len(closed), 3) if closed else None,
            "recent": [fb.to_dict() for fb in recent],
        }


def _type_label(ft: str) -> str:
    return {"like": "👍 有用", "dislike": "👎 不准", "idea": "💡 想法"}.get(ft, ft)


# 进程级单例
feedback_store = FeedbackStore()
