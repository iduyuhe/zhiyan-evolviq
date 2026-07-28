"""免费额度计量器（S2 v30.5 β，#309 S2-1b）—— 内存计数 + 数据库持久化（韧性降级）

免费额度三维（总纲 §3 S2-3）：源数 ≤3（#307 已落地）/ 日信号 ≤50 / 月解读 ≤30。
本模块负责后两维的计量与拦截：

- 日信号（daily_signals）：/environment/feed 出口按「当日去重后的新信号条数」计量。
  同一条信号反复轮询只计一次（去重集内存态）；超出当日余量的信号被截断不下发，
  响应带 quota 块供前端提示——feed 不 402（避免面板轮询雪崩），解读才 402。
- 月解读（monthly_insights）：sessions 三个规划入口（/sessions、/quick-check、
  /multi-agent）各计 1 次；超限抛 UsageExceeded → API 层转 402 + 信任爬梯③文案。

豁免规则（谁不计量）：
1. tenant == "default"：平台/演示/匿名上下文（非 SaaS 注册租户），不计量——
   保证现有匿名调用与全量测试行为不变。
2. 信任爬梯③已达：租户 gateway_config 非空（= 已接第 1 个内部数据源 = 付费线），
   免限额。这正是总纲付费线语义的代码化。
3. ZHIYAN_FREE_TIER_ENFORCE=0：全局关闸（应急/私有化部署）。

韧性：db 不可达时计数仅内存持有（重启清零，方向是「宽松不误伤」）；
持久化 best-effort，失败只告警不阻断业务。
"""

from __future__ import annotations

import logging
import os
import time

from sqlalchemy import select

from src.common import db
from src.runtime.models.tenant import DEFAULT_TENANT_ID
from src.runtime.models.tenant_usage import TenantUsage, usage_pk

logger = logging.getLogger(__name__)

# 免费额度默认值（总纲 §3 S2-3，发布前可调）
FREE_DAILY_SIGNALS = int(os.getenv("ZHIYAN_FREE_DAILY_SIGNALS", "50"))
FREE_MONTHLY_INSIGHTS = int(os.getenv("ZHIYAN_FREE_MONTHLY_INSIGHTS", "30"))
ENFORCE = os.getenv("ZHIYAN_FREE_TIER_ENFORCE", "1") == "1"

METRIC_SIGNALS = "daily_signals"
METRIC_INSIGHTS = "monthly_insights"

UPGRADE_HINT = "接入第 1 个内部数据源即可解锁不限量（信任爬梯③）"


class UsageExceeded(Exception):
    """免费额度超限（API 层转 402）"""

    def __init__(self, metric: str, limit: int):
        self.metric = metric
        self.limit = limit
        label = "本月 agent 解读次数" if metric == METRIC_INSIGHTS else "今日环境信号条数"
        super().__init__(f"免费版{label}已达上限（{limit}）；{UPGRADE_HINT}")


def _period(metric: str) -> str:
    if metric == METRIC_SIGNALS:
        return time.strftime("%Y-%m-%d")
    return time.strftime("%Y-%m")


def _limit(metric: str) -> int:
    # 运行时读模块全局，便于测试 monkeypatch 与热调参
    return FREE_DAILY_SIGNALS if metric == METRIC_SIGNALS else FREE_MONTHLY_INSIGHTS


class UsageMeter:
    """租户用量计量器（进程级单例语义）"""

    def __init__(self) -> None:
        # {pk: used}
        self._counters: dict[str, int] = {}
        # 当日信号去重集 {(tenant, period): set(signal_id)}——内存态，重启即失（保守方向）
        self._seen: dict[tuple[str, str], set[str]] = {}

    # ---------- 生命周期 ----------
    async def init(self) -> None:
        """从库恢复当期计数（main lifespan 在 init_db 之后调用；幂等）。"""
        if not db.db_available or db.async_session is None:
            logger.warning("⚠️ 用量计量降级为内存态（db 不可用），重启清零")
            return
        try:
            periods = {_period(METRIC_SIGNALS), _period(METRIC_INSIGHTS)}
            async with db.async_session() as s:
                rows = (
                    await s.execute(select(TenantUsage).where(TenantUsage.period_key.in_(periods)))
                ).scalars().all()
                for r in rows:
                    self._counters[usage_pk(r.tenant_id, r.metric, r.period_key)] = r.used
            logger.info(f"✅ 用量计数恢复：{len(self._counters)} 条（当期）")
        except Exception as e:
            logger.warning(f"⚠️ 用量计数恢复失败，降级内存态：{e}")

    # ---------- 豁免判定 ----------
    def is_unlimited(self, tenant_id: str) -> bool:
        if not ENFORCE:
            return True
        if tenant_id == DEFAULT_TENANT_ID:
            return True  # 平台/演示上下文，非 SaaS 注册租户
        try:
            from src.runtime.unlock_map import trust_ladder_reached

            if trust_ladder_reached(tenant_id):
                return True  # 信任爬梯③（网关或 BOM，#311 单一语义源）= 付费线，免限额
        except Exception:
            pass
        return False

    # ---------- 查询 ----------
    def used(self, tenant_id: str, metric: str) -> int:
        return self._counters.get(usage_pk(tenant_id, metric, _period(metric)), 0)

    def view(self, tenant_id: str) -> dict:
        """租户额度视图（前端「解锁进度」#310 消费）。"""
        unlimited = self.is_unlimited(tenant_id)
        out: dict = {"tenant_id": tenant_id, "unlimited": unlimited,
                     "upgrade_hint": None if unlimited else UPGRADE_HINT, "metrics": {}}
        for metric in (METRIC_SIGNALS, METRIC_INSIGHTS):
            used = self.used(tenant_id, metric)
            limit = _limit(metric)
            out["metrics"][metric] = {
                "used": used,
                "limit": None if unlimited else limit,
                "remaining": None if unlimited else max(0, limit - used),
                "period": _period(metric),
            }
        return out

    # ---------- 消费 ----------
    async def consume_insight(self, tenant_id: str) -> dict:
        """agent 解读计 1 次；超限抛 UsageExceeded（API → 402）。"""
        if self.is_unlimited(tenant_id):
            return self.view(tenant_id)
        limit = _limit(METRIC_INSIGHTS)
        if self.used(tenant_id, METRIC_INSIGHTS) >= limit:
            raise UsageExceeded(METRIC_INSIGHTS, limit)
        await self._incr(tenant_id, METRIC_INSIGHTS, 1)
        return self.view(tenant_id)

    async def consume_signals(self, tenant_id: str, signals: list[dict]) -> tuple[list[dict], dict]:
        """日信号计量：当日去重后按余量截断。

        返回 (允许下发的信号, quota 块)。feed 永不 402——超限时下发列表为空/截断，
        quota.exhausted=True 由前端提示升级。
        """
        if self.is_unlimited(tenant_id):
            return signals, {"unlimited": True}
        period = _period(METRIC_SIGNALS)
        limit = _limit(METRIC_SIGNALS)
        seen = self._seen.setdefault((tenant_id, period), set())
        used = self.used(tenant_id, METRIC_SIGNALS)

        allowed: list[dict] = []
        new_count = 0
        for ev in signals:
            sid = str(ev.get("id") or ev.get("ts") or id(ev))
            if sid in seen:
                allowed.append(ev)  # 当日已计过，重复轮询免费
                continue
            if used + new_count >= limit:
                continue  # 余量用尽，截断新信号
            seen.add(sid)
            new_count += 1
            allowed.append(ev)
        if new_count:
            await self._incr(tenant_id, METRIC_SIGNALS, new_count)
        used_after = used + new_count
        return allowed, {
            "unlimited": False,
            "metric": METRIC_SIGNALS,
            "used": used_after,
            "limit": limit,
            "remaining": max(0, limit - used_after),
            "truncated": len(signals) - len(allowed),
            "exhausted": used_after >= limit,
            "upgrade_hint": UPGRADE_HINT if used_after >= limit else None,
        }

    # ---------- 内部 ----------
    async def _incr(self, tenant_id: str, metric: str, amount: int) -> None:
        period = _period(metric)
        pk = usage_pk(tenant_id, metric, period)
        self._counters[pk] = self._counters.get(pk, 0) + amount
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    obj = await s.get(TenantUsage, pk)
                    if obj is None:
                        s.add(TenantUsage(id=pk, tenant_id=tenant_id, metric=metric,
                                          period_key=period, used=self._counters[pk]))
                    else:
                        obj.used = self._counters[pk]
                    await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 用量持久化失败（内存已计）：{e}")


# 进程级单例
usage_meter = UsageMeter()
