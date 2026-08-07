"""企业微信自建应用 H5 适配服务（移动端三阶第②阶，2026-08-02 骨架）

职责：
- get_access_token()：企微 access_token（带内存缓存，90 分钟有效提前刷新）
- get_jsapi_ticket()：JS-SDK ticket（agentConfig 签名前置，带缓存）
- sign_agent_config(url)：生成 agentConfig 签名（jsapi_ticket + noncestr + timestamp + url → sha1）
- send_app_message(userids, content)：应用消息推送（工作通知，缺料预警场景）

🔴 凭证铁律：corpid/secret/agentid 只读 `settings`（服务器 .env），绝不进代码/日志/响应。
🔴 优雅降级：任一凭证缺失 → 所有方法返回 None / status=unconfigured，绝不抛异常、绝不阻塞平台。
🔴 网络 import 延迟（韧性铁律）；外部 API 失败静默降级。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time

logger = logging.getLogger(__name__)

# 企微 API 基础
_WECOM_API = "https://qyapi.weixin.qq.com/cgi-bin"
# token/ticket 提前刷新窗口（秒）
_TOKEN_LIFETIME = 7200  # 企微默认 2 小时
_TOKEN_REFRESH_BEFORE = 300


class WeComService:
    """企业微信自建应用适配（配置缺失时优雅降级）。"""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._access_token_exp: float = 0.0
        self._jsapi_ticket: str | None = None
        self._jsapi_ticket_exp: float = 0.0

    # ---------- 配置 ----------

    @property
    def configured(self) -> bool:
        try:
            from src.common.config import settings

            return bool(settings.wecom_corpid and settings.wecom_secret and settings.wecom_agentid)
        except Exception:
            return False

    def status(self) -> dict:
        try:
            from src.common.config import settings

            return {
                "configured": self.configured,
                "corpid_set": bool(settings.wecom_corpid),
                "secret_set": bool(settings.wecom_secret),
                "agentid_set": bool(settings.wecom_agentid),
                # 🔴 绝不返回凭证明文
                "mode": "live" if self.configured else "unconfigured",
                "detail": "已配置（企微免登+推送可用）" if self.configured
                else "未配置企微凭证：在服务器 .env 填 wecom_corpid/secret/agentid 后重启生效",
            }
        except Exception as e:  # pragma: no cover - 防御
            return {"configured": False, "mode": "unconfigured", "detail": str(e)}

    # ---------- access_token（带缓存） ----------

    async def get_access_token(self) -> str | None:
        if not self.configured:
            return None
        if self._access_token and time.time() < self._access_token_exp - _TOKEN_REFRESH_BEFORE:
            return self._access_token
        try:
            import httpx  # 延迟 import（韧性铁律）

            from src.common.config import settings

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{_WECOM_API}/gettoken",
                    params={
                        "corpid": settings.wecom_corpid,
                        "corpsecret": settings.wecom_secret,
                    },
                )
                data = resp.json()
            if data.get("errcode") not in (0, None):
                logger.warning(f"⚠️ [wecom] gettoken 失败 errcode={data.get('errcode')} errmsg={data.get('errmsg')}")
                return None
            token = data.get("access_token")
            if not token:
                return None
            expires_in = int(data.get("expires_in", _TOKEN_LIFETIME))
            self._access_token = token
            self._access_token_exp = time.time() + expires_in
            return token
        except Exception as e:
            logger.warning(f"⚠️ [wecom] get_access_token 失败（不破管）：{e}")
            return None

    # ---------- JS-SDK ticket（agentConfig 签名前置） ----------

    async def get_jsapi_ticket(self) -> str | None:
        if not self.configured:
            return None
        if self._jsapi_ticket and time.time() < self._jsapi_ticket_exp - _TOKEN_REFRESH_BEFORE:
            return self._jsapi_ticket
        token = await self.get_access_token()
        if not token:
            return None
        try:
            import httpx

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{_WECOM_API}/get_jsapi_ticket",
                    params={"access_token": token},
                )
                data = resp.json()
            if data.get("errcode") not in (0, None):
                logger.warning(f"⚠️ [wecom] get_jsapi_ticket errcode={data.get('errcode')}")
                return None
            ticket = data.get("ticket")
            if not ticket:
                return None
            self._jsapi_ticket = ticket
            self._jsapi_ticket_exp = time.time() + int(data.get("expires_in", _TOKEN_LIFETIME))
            return ticket
        except Exception as e:
            logger.warning(f"⚠️ [wecom] get_jsapi_ticket 失败（不破管）：{e}")
            return None

    # ---------- agentConfig 签名（免登） ----------

    async def sign_agent_config(self, url: str) -> dict | None:
        """生成企微 agentConfig 所需签名。凭证缺失返回 None。

        签名算法（企微官方）：jsapi_ticket + noncestr + timestamp + url → SHA1。
        """
        ticket = await self.get_jsapi_ticket()
        if not ticket:
            return None
        from src.common.config import settings

        noncestr = secrets.token_hex(8)
        timestamp = str(int(time.time()))
        raw = f"jsapi_ticket={ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}"
        signature = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        return {
            "corpid": settings.wecom_corpid,
            "agentId": settings.wecom_agentid,
            "nonceStr": noncestr,
            "timestamp": timestamp,
            "signature": signature,
            "url": url,
        }

    # ---------- 应用消息推送（缺料预警等） ----------

    async def send_app_message(self, userids: list[str], content: str, title: str = "智衍 EvolvIQ 预警") -> dict:
        """给企微成员发应用消息（工作通知）。凭证缺失返回降级 dict。

        msgtype=textcard（卡片，可带跳转 URL）。userids 为空 → 按部门/全员需另扩展。
        """
        if not self.configured or not userids:
            return {"ok": False, "reason": "unconfigured_or_empty"}
        token = await self.get_access_token()
        if not token:
            return {"ok": False, "reason": "token_failed"}
        try:
            import httpx

            body = {
                "touser": "|".join(userids[:1000]),  # 企微上限 1000
                "msgtype": "textcard",
                "agentid": int(self._agentid()),
                "textcard": {
                    "title": title[:128],
                    "description": content[:512],
                    "url": "https://zhiyan.weomnitech.com.cn/",  # 点击跳平台
                    "btntxt": "查看详情",
                },
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{_WECOM_API}/message/send",
                    params={"access_token": token},
                    json=body,
                )
                data = resp.json()
            if data.get("errcode") not in (0, None):
                logger.warning(f"⚠️ [wecom] message/send errcode={data.get('errcode')} errmsg={data.get('errmsg')}")
                return {"ok": False, "reason": f"wecom_error:{data.get('errcode')}", "detail": data.get("errmsg")}
            return {"ok": True, "msgid": data.get("msgid")}
        except Exception as e:
            logger.warning(f"⚠️ [wecom] send_app_message 失败（不破管）：{e}")
            return {"ok": False, "reason": "exception", "detail": str(e)}

    def _agentid(self) -> str:
        try:
            from src.common.config import settings

            return str(settings.wecom_agentid)
        except Exception:
            return ""

    # ---------- OAuth：扫码即联拿 userid ----------

    async def get_userid_by_oauth_code(self, code: str) -> str | None:
        """企微网页授权（snsapi_base）code → userid。

        用于「扫码即联」确认环节：用户在企微内打开确认页，企微带 code 回跳，
        后端用 code 换成员 userid（不暴露手机号/姓名）。失败返回 None（优雅降级）。
        """
        if not self.configured or not code:
            return None
        token = await self.get_access_token()
        if not token:
            return None
        try:
            import httpx

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"{_WECOM_API}/auth/getuserinfo",
                    params={"access_token": token, "code": code},
                )
                data = resp.json()
            if data.get("errcode") not in (0, None):
                logger.warning(f"⚠️ [wecom] getuserinfo errcode={data.get('errcode')}")
                return None
            return data.get("userid") or None
        except Exception as e:
            logger.warning(f"⚠️ [wecom] get_userid_by_oauth_code 失败（不破管）：{e}")
            return None

    # ---------- 审批卡片（人留终审 · 移动端按钮回调） ----------

    def build_approval_card(self, session_id: str, title: str, summary: str, tenant: str) -> dict:
        """构造「按钮交互」模板卡片（template_card.button_interaction）。

        卡片含「通过 / 驳回」两个按钮，事件键 EventKey 编码 session_id，
        用户在企微内点击 → 回调带来 EventKey → im_bridge 路由到 engine.execute/reject。

        🔴 卡片内容须经 im_bridge.sanitize_im_text 脱敏后再传入（此处不负责脱敏，
        由调用方保证）；本方法只负责结构。
        """
        return {
            "msgtype": "template_card",
            "template_card": {
                "card_type": "button_interaction",
                "main_title": {
                    "title": (title or "待审批决策")[:40],
                    "desc": (tenant or "")[:40],
                },
                "sub_title_text": (summary or "")[:120],
                "task_id": session_id,  # 用于回调关联
                "button_list": [
                    {
                        "text": "通过",
                        "style": 1,  # 绿色
                        "key": f"APPROVE:{session_id}",
                    },
                    {
                        "text": "驳回",
                        "style": 2,  # 红色
                        "key": f"REJECT:{session_id}",
                    },
                ],
            },
        }

    def build_result_card(self, title: str, content: str) -> dict:
        """构造「文本通知」模板卡片（template_card.text_notice），用于审批结果回执。"""
        return {
            "msgtype": "template_card",
            "template_card": {
                "card_type": "text_notice",
                "main_title": {"title": (title or "执行结果")[:40]},
                "sub_title_text": (content or "")[:512],
                "card_action": {
                    "type": 1,
                    "url": "https://zhiyan.weomnitech.com.cn/",
                },
            },
        }

    async def send_template_card(self, userids: list[str], card: dict) -> dict:
        """推送模板卡片（审批卡片 / 结果回执）。凭证缺失返回降级 dict。

        与 send_app_message 一致：touser 竖线拼接（上限 1000），失败优雅降级不破管。
        """
        if not self.configured or not userids or not card:
            return {"ok": False, "reason": "unconfigured_or_empty"}
        token = await self.get_access_token()
        if not token:
            return {"ok": False, "reason": "token_failed"}
        try:
            import httpx

            body = {
                "touser": "|".join(userids[:1000]),
                "msgtype": "template_card",
                "agentid": int(self._agentid()),
                "template_card": card["template_card"],
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{_WECOM_API}/message/send",
                    params={"access_token": token},
                    json=body,
                )
                data = resp.json()
            if data.get("errcode") not in (0, None):
                logger.warning(f"⚠️ [wecom] template_card send errcode={data.get('errcode')}")
                return {"ok": False, "reason": f"wecom_error:{data.get('errcode')}", "detail": data.get("errmsg")}
            return {"ok": True, "msgid": data.get("msgid")}
        except Exception as e:
            logger.warning(f"⚠️ [wecom] send_template_card 失败（不破管）：{e}")
            return {"ok": False, "reason": "exception", "detail": str(e)}


# 进程级单例
wecom_service = WeComService()
