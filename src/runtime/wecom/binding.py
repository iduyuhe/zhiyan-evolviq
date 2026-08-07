"""扫码即联绑定模块（IM 对接 · 像 WorkBuddy 那样扫码即可联接，2026-08-03）

职责：
- 生成一次性、短期有效的绑定令牌（QR 编码），用户在企微内扫码打开确认页即完成绑定；
- 维护 租户 ↔ 企业微信 corp_id ↔ 成员 userid 三方映射，供审批卡片路由与租户归属判定；
- 内存存储（演示态），优雅降级（未配置企微时仍可建令牌，确认环节需 corp 信息）；
- 🔴 fail-closed：corp→tenant 解析失败一律返回 None（拒绝任何跨租户推断）。

绑定流程（与 WorkBuddy 体验对齐）：
1. 平台管理员/租户管理员在 Web 端点击「生成绑定二维码」→ create_bind_session(tenant)
   返回 token + confirm_url（二维码载荷）。
2. 用户在企微内扫码 → 打开 confirm_url（走企微 OAuth 拿 code）→ GET /wecom/bind/confirm?token=&code=
3. 后端用 code 换 userid，confirm_bind(token, corp_id, userid) 落库映射 → 绑定完成。
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 绑定令牌有效期（秒）：扫码即联强调「即时」，过期需重新生成
_BIND_TTL = 300
# 确认页基址（与 nginx/边缘一致）；corp 由企微 OAuth 回跳时带入
_CONFIRM_BASE = "https://zhiyan.weomnitech.com.cn"


@dataclass
class BindSession:
    """一次性绑定会话：token 短期有效，确认后写入映射。"""

    token: str
    tenant: str
    created_at: float
    corp_id: str | None = None
    created_by: str | None = None
    confirmed: bool = False
    confirmed_at: float | None = None
    userid: str | None = None
    failed_reason: str | None = None

    def is_expired(self, now: float | None = None) -> bool:
        now = now or time.time()
        return (now - self.created_at) > _BIND_TTL


class BindingStore:
    """租户↔corp↔userid 绑定映射（内存态，进程级单例）。

    演示态够用；生产可替换为 Redis/PG。所有解析方法 fail-closed。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BindSession] = {}
        self._corp_to_tenant: dict[str, str] = {}
        self._user_to_tenant: dict[str, str] = {}
        self._tenant_to_userids: dict[str, set[str]] = {}

    # ---------- 生成绑定会话（Web 端调用） ----------

    def create_bind_session(self, tenant: str, created_by: str | None = None) -> BindSession:
        token = secrets.token_urlsafe(16)
        s = BindSession(token=token, tenant=tenant, created_at=time.time(), created_by=created_by)
        self._sessions[token] = s
        self._gc()
        return s

    def build_qr_payload(self, token: str, corp_id_hint: str | None = None) -> dict:
        """构造二维码载荷：用户扫码后打开的确认链接 + 元数据。

        corp_id_hint 可选（Web 端已知 corp 时预填，OAuth 回跳时以实际为准）。
        """
        confirm_url = f"{_CONFIRM_BASE}/wecom/bind/confirm?token={token}"
        if corp_id_hint:
            confirm_url += f"&corp={corp_id_hint}"
        return {
            "token": token,
            "confirm_url": confirm_url,
            "ttl": _BIND_TTL,
            "corp_id_hint": corp_id_hint,
            # 二维码文本即 confirm_url；前端用 qrcode 库生成图片
        }

    # ---------- 确认绑定（企微 OAuth 回跳调用） ----------

    def confirm_bind(self, token: str, corp_id: str, userid: str) -> dict:
        s = self._sessions.get(token)
        if not s:
            return {"ok": False, "reason": "token_not_found"}
        if s.confirmed:
            return {"ok": False, "reason": "already_confirmed"}
        if s.is_expired():
            s.failed_reason = "token_expired"
            return {"ok": False, "reason": "token_expired"}
        if not corp_id or not userid:
            s.failed_reason = "missing_corp_or_userid"
            return {"ok": False, "reason": "missing_corp_or_userid"}
        # 落库三方映射
        s.confirmed = True
        s.confirmed_at = time.time()
        s.corp_id = corp_id
        s.userid = userid
        self._corp_to_tenant[corp_id] = s.tenant
        self._user_to_tenant[userid] = s.tenant
        self._tenant_to_userids.setdefault(s.tenant, set()).add(userid)
        logger.info(f"✅ 企微绑定完成：corp={corp_id} user={userid} → tenant={s.tenant}")
        return {"ok": True, "tenant": s.tenant, "userid": userid}

    # ---------- 解析（fail-closed） ----------

    def resolve_tenant_by_corp(self, corp_id: str | None) -> str | None:
        """corp_id → tenant。无绑定记录一律 None（绝不推断/回落）。"""
        if not corp_id:
            return None
        return self._corp_to_tenant.get(corp_id)

    def resolve_tenant_by_user(self, userid: str | None) -> str | None:
        if not userid:
            return None
        return self._user_to_tenant.get(userid)

    def resolve_approver_userid(self, tenant: str, corp_id: str | None = None) -> str | None:
        """取租户的首位审批人 userid（用于推送审批卡片）。多审批人时返回第一个。"""
        ids = self._tenant_to_userids.get(tenant)
        if ids:
            return next(iter(ids))
        return None

    def approver_userids(self, tenant: str) -> list[str]:
        return list(self._tenant_to_userids.get(tenant, set()))

    def is_bound(self, tenant: str) -> bool:
        return bool(self._tenant_to_userids.get(tenant))

    def is_user_bound(self, userid: str) -> bool:
        return userid in self._user_to_tenant

    # ---------- 清理 ----------

    def _gc(self) -> None:
        """回收过期未确认的绑定会话，避免内存无限增长。"""
        now = time.time()
        expired = [t for t, s in self._sessions.items() if not s.confirmed and s.is_expired(now)]
        for t in expired:
            self._sessions.pop(t, None)


# 进程级单例
binding_store = BindingStore()
