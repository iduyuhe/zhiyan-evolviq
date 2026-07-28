"""S3-1 行为埋点基座——行为事件存储 + 租户行为画像（#315）

内存权威 + DB best-effort 持久化（与 feedback_store / platform_insight_store 同构）：
- db 可用：事件落库（behavior_events 表），重启后恢复（只回灌最近 _LOAD_LIMIT 条）。
- db 不可达：仅内存持有，重启即失——绝不因埋点失败阻断业务主流程。

三大职责：
1. record()：记录一条行为事件（fire-and-forget 语义，异常吞掉只告警）。
2. events_for()：本租户事件流（推荐层 1-4 的原始燃料）。
3. profile()：本租户行为画像聚合（事件类型分布 / 关注对象 Top / 活跃用户数 /
   近 7 天活跃度）——供 S3-2 相关性打分与 S3-5 无感转型导航器消费。

🔴 隐私红线（MASTER §S3）：
- 画像仅存于本租户、仅用于本租户推荐；所有查询强制按 tenant_id 过滤。
- 绝不提供跨租户聚合到个体可识别粒度的任何接口。
- meta 只存轻量上下文，record() 侧截断到 _META_MAX 字符。
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from src.common import db
from src.runtime.models.behavior_event import BehaviorEvent

logger = logging.getLogger(__name__)

_MEM_MAX = 5000     # 内存事件池上限（全局，超限淘汰最旧）
_LOAD_LIMIT = 2000  # 启动回灌上限（最近 N 条）
_META_MAX = 400     # meta JSON 文本截断上限


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BehaviorStore:
    """行为事件注册表（进程级单例语义）"""

    def __init__(self) -> None:
        self._events: list[BehaviorEvent] = []  # 按插入序（≈时间序）

    # ---------- 生命周期 ----------
    async def init(self) -> None:
        """从库回灌最近事件到内存（main lifespan 在 init_db 之后调用；幂等）。"""
        self._events = []
        if not db.db_available or db.async_session is None:
            logger.warning("⚠️ 行为埋点存储降级为内存态（db 不可用），重启即失")
            return
        try:
            async with db.async_session() as s:
                rows = (
                    await s.execute(
                        select(BehaviorEvent).order_by(BehaviorEvent.created_at.desc()).limit(_LOAD_LIMIT)
                    )
                ).scalars().all()
                self._events = list(reversed(rows))  # 恢复时间正序
            logger.info(f"✅ 行为事件回灌：{len(self._events)} 条")
        except Exception as e:
            logger.warning(f"⚠️ 行为事件回灌失败，降级内存态：{e}")

    # ---------- 写入（fire-and-forget：绝不阻断业务主流程） ----------
    async def record(
        self,
        tenant_id: str,
        event_type: str,
        user_id: str | None = None,
        object_kind: str | None = None,
        object_id: str | None = None,
        meta: dict | None = None,
    ) -> dict | None:
        """记录一条行为事件。任何异常只告警不上抛（埋点失败≠业务失败）。"""
        try:
            if not tenant_id or not event_type:
                return None
            meta_text: str | None = None
            if meta:
                try:
                    meta_text = json.dumps(meta, ensure_ascii=False)[:_META_MAX]
                except Exception:
                    meta_text = None
            ev = BehaviorEvent(
                id=uuid.uuid4().hex,
                tenant_id=tenant_id,
                user_id=user_id,
                event_type=event_type.strip().lower()[:32],
                object_kind=(object_kind or None),
                object_id=(object_id[:128] if object_id else None),
                meta=meta_text,
                created_at=_now(),  # 内存态即时可用（DB 侧 server_default 兜底）
            )
            self._events.append(ev)
            if len(self._events) > _MEM_MAX:
                self._events = self._events[-_MEM_MAX:]
            await self._persist(ev)
            return ev.to_dict()
        except Exception as e:  # 埋点绝不影响主流程
            logger.warning(f"⚠️ 行为事件记录失败（已忽略）：{e}")
            return None

    async def _persist(self, ev: BehaviorEvent) -> None:
        if not (db.db_available and db.async_session is not None):
            return
        try:
            async with db.async_session() as s:
                s.add(ev)
                await s.commit()
        except Exception as e:
            logger.warning(f"⚠️ 行为事件持久化失败（内存已更新）：{e}")

    # ---------- 查询（强制租户过滤） ----------
    def events_for(
        self,
        tenant_id: str,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """本租户事件流（时间倒序）。"""
        out = [
            ev.to_dict()
            for ev in reversed(self._events)
            if ev.tenant_id == tenant_id and (event_type is None or ev.event_type == event_type)
        ]
        return out[: max(1, min(limit, 500))]

    # ---------- 画像（本租户内聚合；🔴 绝不跨租户） ----------
    def profile(self, tenant_id: str, days: int = 30) -> dict:
        """本租户行为画像：事件分布 / 关注对象 Top5 / 活跃用户 / 近 7 天活跃。"""
        cutoff = _now() - timedelta(days=max(1, min(days, 90)))
        items = [
            ev for ev in self._events
            if ev.tenant_id == tenant_id and ev.created_at and _aware(ev.created_at) >= cutoff
        ]
        type_counts = Counter(ev.event_type for ev in items)
        obj_counts = Counter(
            f"{ev.object_kind}:{ev.object_id}" for ev in items if ev.object_kind and ev.object_id
        )
        users = {ev.user_id for ev in items if ev.user_id}
        week_cutoff = _now() - timedelta(days=7)
        recent7 = sum(1 for ev in items if ev.created_at and _aware(ev.created_at) >= week_cutoff)
        return {
            "tenant_id": tenant_id,
            "window_days": days,
            "total_events": len(items),
            "event_types": dict(type_counts),
            "top_objects": [
                {"object": k, "count": c} for k, c in obj_counts.most_common(5)
            ],
            "active_users": len(users),
            "events_last_7d": recent7,
            "generated_at": _now().isoformat(),
        }

    async def patch_meta(
        self,
        tenant_id: str,
        event_type: str,
        object_id: str,
        patch: dict,
    ) -> bool:
        """更新 (tenant, event_type, object_id) 最新一条事件的 meta（合并 patch）。

        用于共生环反馈状态机（submitted→in_progress→released）等需"原地更新"的场景。
        DB 与内存同步更新；DB 不可达则仅内存生效（与 record 同级韧性）。
        🔴 严格按 tenant 过滤，绝不跨租户。
        """
        if not tenant_id or not event_type or not object_id:
            return False
        target = None
        for ev in reversed(self._events):
            if (
                ev.tenant_id == tenant_id
                and ev.event_type == event_type
                and ev.object_id == object_id
            ):
                target = ev
                break
        if target is None:
            return False
        cur: dict = {}
        if target.meta:
            try:
                cur = json.loads(target.meta)
            except Exception:
                cur = {}
        cur.update(patch)
        meta_text = json.dumps(cur, ensure_ascii=False)[:_META_MAX]
        target.meta = meta_text
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    await s.execute(
                        text("UPDATE behavior_events SET meta=:m WHERE id=:i"),
                        {"m": meta_text, "i": target.id},
                    )
                    await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 行为事件 meta 更新失败（内存已更新）：{e}")
        return True

    def first_event_at(self, tenant_id: str) -> str | None:
        """本租户最早事件时间（ISO），无则返回 None。供成长档案『使用天数』。"""
        ts = [
            ev.created_at
            for ev in self._events
            if ev.tenant_id == tenant_id and ev.created_at
        ]
        return min(ts).isoformat() if ts else None

    # ---------- 测试清理 ----------
    def clear_memory(self, tenant_id: str | None = None) -> int:
        """清内存事件（测试用；tenant_id=None 清全部）。不动 DB。"""
        before = len(self._events)
        if tenant_id is None:
            self._events = []
        else:
            self._events = [ev for ev in self._events if ev.tenant_id != tenant_id]
        return before - len(self._events)


def _aware(dt: datetime) -> datetime:
    """SQLite 回灌的 created_at 可能是 naive UTC——统一补时区再比较。"""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# 进程级单例
behavior_store = BehaviorStore()
