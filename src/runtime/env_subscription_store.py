"""环境订阅规则存储（S2 v30.5 β）—— 内存注册表 + 数据库持久化（韧性降级）

与 tenant_store 同构：
- db 可用：规则落库（env_subscriptions 表），重启后恢复。
- db 不可用：仅内存持有，多租户筛选逻辑仍可运行，重启即失。

核心职责：
1. CRUD（tenant-scoped，upsert 语义：一租户一源一行）。
2. 免费额度上限：启用源数 ≤ FREE_MAX_SOURCES（默认 4，ZHIYAN_FREE_MAX_ENV_SOURCES 可调）
   —— 超限抛 QuotaExceeded，API 层转 402（付费线=信任爬梯③）。
3. 语义隔离筛选 filter_signals()：「抓取共享、语义隔离」两层制的消费层——
   平台级信号池按租户订阅规则（源开关/credibility 阈值/关键词）过滤出租户可见流。
   无任何订阅记录的租户走「行业默认模板」：三源全启用、credibility_min=general。
"""

from __future__ import annotations

import json
import logging
import os
import uuid

from sqlalchemy import select

from src.common import db
from src.runtime.models.env_subscription import CRED_RANK, EnvSubscription

logger = logging.getLogger(__name__)

# 免费额度：最多启用的环境信息源数（总纲 §3 S2-3，发布前杜总可调）
# 2026-08-02 方案 A：新增 customer_voice（客户声音）源后默认模板 4 源 → 免费额度 3→4。
# 免费圈=「纯⑥信号」公开源，客户声音(商机情报)是免费圈钩子，不算破坏免费承诺。
FREE_MAX_SOURCES = int(os.getenv("ZHIYAN_FREE_MAX_ENV_SOURCES", "4"))


class QuotaExceeded(Exception):
    """免费额度超限（API 层转 402）"""


def _default_rule(source_name: str, tenant_id: str) -> dict:
    """行业默认模板：未显式配置的源按此规则（全启用、全收、1 小时轮询）。"""
    return {
        "id": None,
        "tenant_id": tenant_id,
        "source_name": source_name,
        "enabled": True,
        "credibility_min": "general",
        "keywords_include": [],
        "keywords_exclude": [],
        "poll_interval_sec": 3600,
        "is_default": True,
    }


class EnvSubscriptionStore:
    """订阅规则注册表（进程级单例语义）"""

    def __init__(self) -> None:
        # {tenant_id: {source_name: EnvSubscription}}
        self._by_tenant: dict[str, dict[str, EnvSubscription]] = {}

    # ---------- 生命周期 ----------
    async def init(self) -> None:
        """从库加载全部订阅规则到内存（main lifespan 在 init_db 之后调用；幂等）。"""
        if not db.db_available or db.async_session is None:
            logger.warning("⚠️ 环境订阅存储降级为内存态（db 不可用），重启即失")
            return
        try:
            async with db.async_session() as s:
                rows = (await s.execute(select(EnvSubscription))).scalars().all()
                for r in rows:
                    self._by_tenant.setdefault(r.tenant_id, {})[r.source_name] = r
            logger.info(f"✅ 环境订阅规则加载：{sum(len(v) for v in self._by_tenant.values())} 条")
        except Exception as e:
            logger.warning(f"⚠️ 环境订阅加载失败，降级内存态：{e}")

    # ---------- 查询 ----------
    def list_for(self, tenant_id: str, known_sources: list[str] | None = None) -> list[dict]:
        """租户订阅视图：显式规则 + 未配置源的默认模板（is_default=True 标记）。"""
        explicit = self._by_tenant.get(tenant_id, {})
        out = [sub.to_dict() for sub in explicit.values()]
        for name in known_sources or []:
            if name not in explicit:
                out.append(_default_rule(name, tenant_id))
        return sorted(out, key=lambda d: d["source_name"])

    def get(self, tenant_id: str, source_name: str) -> EnvSubscription | None:
        return self._by_tenant.get(tenant_id, {}).get(source_name)

    def enabled_count(self, tenant_id: str, known_sources: list[str] | None = None) -> int:
        """当前启用源数（含默认模板视为启用——默认全启即已占额度）。"""
        return sum(1 for r in self.list_for(tenant_id, known_sources) if r["enabled"])

    # ---------- 写入 ----------
    async def upsert(
        self,
        tenant_id: str,
        source_name: str,
        *,
        enabled: bool = True,
        credibility_min: str = "general",
        keywords_include: list[str] | None = None,
        keywords_exclude: list[str] | None = None,
        poll_interval_sec: int = 3600,
        known_sources: list[str] | None = None,
    ) -> dict:
        """新建/更新订阅规则。免费额度：启用源数不得超过 FREE_MAX_SOURCES。"""
        if credibility_min not in CRED_RANK:
            raise ValueError(f"credibility_min 须为 {list(CRED_RANK)} 之一")
        poll_interval_sec = max(60, int(poll_interval_sec))  # 下限 1 分钟（成本保护）

        # 免费额度校验：模拟本次变更后的启用源数
        if enabled:
            after = {
                r["source_name"]: r["enabled"] for r in self.list_for(tenant_id, known_sources)
            }
            after[source_name] = True
            if sum(1 for v in after.values() if v) > FREE_MAX_SOURCES:
                raise QuotaExceeded(
                    f"免费版最多启用 {FREE_MAX_SOURCES} 个信息源；"
                    f"接入第 1 个内部数据源即可解锁更多（信任爬梯③）"
                )

        sub = self.get(tenant_id, source_name)
        if sub is None:
            sub = EnvSubscription(
                id=uuid.uuid4().hex[:16], tenant_id=tenant_id, source_name=source_name
            )
            self._by_tenant.setdefault(tenant_id, {})[source_name] = sub
        sub.enabled = enabled
        sub.credibility_min = credibility_min
        sub.keywords_include = json.dumps(keywords_include or [], ensure_ascii=False)
        sub.keywords_exclude = json.dumps(keywords_exclude or [], ensure_ascii=False)
        sub.poll_interval_sec = poll_interval_sec

        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    obj = await s.get(EnvSubscription, sub.id)
                    if obj is None:
                        s.add(
                            EnvSubscription(
                                id=sub.id,
                                tenant_id=sub.tenant_id,
                                source_name=sub.source_name,
                                enabled=sub.enabled,
                                credibility_min=sub.credibility_min,
                                keywords_include=sub.keywords_include,
                                keywords_exclude=sub.keywords_exclude,
                                poll_interval_sec=sub.poll_interval_sec,
                            )
                        )
                    else:
                        obj.enabled = sub.enabled
                        obj.credibility_min = sub.credibility_min
                        obj.keywords_include = sub.keywords_include
                        obj.keywords_exclude = sub.keywords_exclude
                        obj.poll_interval_sec = sub.poll_interval_sec
                    await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 环境订阅持久化失败（内存已更新）：{e}")
        return sub.to_dict()

    async def delete(self, tenant_id: str, source_name: str) -> bool:
        """删除显式规则（回落行业默认模板）。"""
        sub = self._by_tenant.get(tenant_id, {}).pop(source_name, None)
        if sub is None:
            return False
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    obj = await s.get(EnvSubscription, sub.id)
                    if obj:
                        await s.delete(obj)
                        await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 环境订阅删除持久化失败（内存已移除）：{e}")
        return True

    # ---------- 语义隔离筛选（消费层） ----------
    def filter_signals(
        self, tenant_id: str, signals: list[dict], known_sources: list[str] | None = None
    ) -> list[dict]:
        """按租户订阅规则过滤平台级信号池 → 租户可见流。

        信号 source 形如 env://{kind}/{name}；规则匹配 name。
        规则：源 enabled + credibility >= credibility_min + 关键词 include/exclude。
        """
        rules = {r["source_name"]: r for r in self.list_for(tenant_id, known_sources)}
        out = []
        for ev in signals:
            src = str(ev.get("source", ""))
            name = src.rsplit("/", 1)[-1] if src.startswith("env://") else src
            rule = rules.get(name)
            if rule is None:
                # 未知源（规则外）：保守放行 official，其余不进租户流
                if ev.get("credibility") == "official":
                    out.append(ev)
                continue
            if not rule["enabled"]:
                continue
            cred = str(ev.get("credibility") or "general")
            if CRED_RANK.get(cred, 0) < CRED_RANK.get(rule["credibility_min"], 1):
                continue
            text = json.dumps(ev.get("payload", {}), ensure_ascii=False) + " ".join(
                str(x) for x in ev.get("entities", [])
            )
            inc = rule["keywords_include"]
            if inc and not any(k in text for k in inc):
                continue
            if any(k in text for k in rule["keywords_exclude"]):
                continue
            out.append(ev)
        return out


# 进程级单例
env_subscription_store = EnvSubscriptionStore()
