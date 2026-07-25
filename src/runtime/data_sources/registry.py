"""DataSource 注册表——P1 连接器与 P2 图谱/多租户的接入总线

- 按 (tenant_id, kind, name) 索引所有已配置数据源。
- 韧性：注册/查询永远不抛异常；某个源不可达，get() 返回 None，调用方回退 seed。
- 多租户：get_for_tenant(tenant_id) 返回该租户数据源视图；缺省回退 default。
- 进程级单例 `registry`。
"""

import logging
from typing import Optional

from src.runtime.data_sources.base import DataSource, DataSourceKind, HolonKind

logger = logging.getLogger(__name__)


class DataSourceRegistry:
    """数据源注册表（进程级单例语义）。"""

    def __init__(self):
        # key: "tenant:kind:name" -> DataSource
        self._sources: dict[str, DataSource] = {}
        # tenant -> kind -> DataSource（快速视图）
        self._by_tenant: dict[str, dict[str, DataSource]] = {}

    def register(self, src: DataSource) -> None:
        """注册一个数据源（幂等：同 key 覆盖）。"""
        if not isinstance(src, DataSource):
            logger.warning(f"⚠️ 忽略非 DataSource 对象：{src!r}")
            return
        key = src._key()
        self._sources[key] = src
        self._by_tenant.setdefault(src.tenant_id, {})[src.kind.value] = src
        logger.info(f"📥 注册数据源 {key}")

    def get(
        self,
        kind: DataSourceKind | str,
        tenant_id: str = "default",
        name: str | None = None,
    ) -> Optional[DataSource]:
        """按 kind 取某租户的数据源；tenant 缺配置则回退 default：tenant。"""
        kind_v = kind.value if isinstance(kind, DataSourceKind) else str(kind)
        # 先本租户
        view = self._by_tenant.get(tenant_id, {})
        if kind_v in view:
            return view[kind_v]
        # 回退 default 租户
        if tenant_id != "default":
            view = self._by_tenant.get("default", {})
            if kind_v in view:
                return view[kind_v]
        return None

    def get_for_tenant(self, tenant_id: str) -> dict[str, DataSource]:
        """返回某租户的数据源视图（含 default 回退合并）。"""
        merged: dict[str, DataSource] = {}
        merged.update(self._by_tenant.get("default", {}))
        merged.update(self._by_tenant.get(tenant_id, {}))
        return merged

    def list(self, tenant_id: str | None = None) -> list[DataSource]:
        if tenant_id is None:
            return list(self._sources.values())
        view = self.get_for_tenant(tenant_id)
        return list(view.values())

    # ---- 孪生体状态上行路由（twin_feed）----
    def route_event(
        self,
        holon_kind: "str | HolonKind",
        values: dict,
        source: str | None = None,
        tenant_id: str = "default",
    ) -> int:
        """把一条实时状态上行路由到该 holon 的所有孪生体（DataSource）。

        这是「网关实时流进 agent 推理」的最小落地：网关/外部事件归一为
        (holon_kind, values) 后调用本方法，对应孪生体的 twin_state 被刷新。
        Returns: 成功 ingest 的孪生体数量（韧性：单个失败不影响其他）。
        """
        hk = holon_kind.value if isinstance(holon_kind, HolonKind) else str(holon_kind)
        n = 0
        for src in self.get_for_tenant(tenant_id).values():
            h = getattr(src, "holon_kind", None)
            if h and h.value == hk:
                try:
                    src.ingest(values, source=source)
                    n += 1
                except Exception:
                    pass
        if n:
            logger.debug(f"twin_feed 路由 {hk} → {n} 个孪生体")
        return n

    def get_twin_state(self, holon_kind, tenant_id: str = "default") -> dict | None:
        hk = holon_kind.value if isinstance(holon_kind, HolonKind) else str(holon_kind)
        for src in self.get_for_tenant(tenant_id).values():
            h = getattr(src, "holon_kind", None)
            if h and h.value == hk:
                return src.get_twin_state()
        return None

    def all_twin_states(self, tenant_id: str = "default") -> dict:
        """汇总该租户所有孪生体的最新状态快照（供 agent 推理读取）。"""
        out: dict = {}
        for src in self.get_for_tenant(tenant_id).values():
            h = getattr(src, "holon_kind", None)
            if h:
                out[f"{h.value}:{src.name}"] = src.get_twin_state()
        return out

    async def health(self) -> dict:
        out = {}
        for key, src in self._sources.items():
            try:
                out[key] = await src.health()
            except Exception as e:
                out[key] = {"name": src.name, "error": str(e)}
        return out

    def unregister(self, kind: DataSourceKind | str, tenant_id: str = "default") -> None:
        kind_v = kind.value if isinstance(kind, DataSourceKind) else str(kind)
        view = self._by_tenant.get(tenant_id)
        if view and kind_v in view:
            src = view.pop(kind_v)
            self._sources.pop(src._key(), None)

    def clear(self) -> None:
        """清空（测试用）。"""
        self._sources.clear()
        self._by_tenant.clear()


# 进程级单例
registry = DataSourceRegistry()
