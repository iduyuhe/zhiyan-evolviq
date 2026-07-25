"""数据源配置装载器——环境变量驱动 + 多租户 + API 注入

环境变量的约定（默认租户）：
    ZHIYAN_DS_MES_URL / ZHIYAN_DS_MES_KEY
    ZHIYAN_DS_ERP_URL / ZHIYAN_DS_ERP_KEY
    ZHIYAN_DS_PLM_URL / ZHIYAN_DS_PLM_KEY
    ZHIYAN_DS_WMS_URL / ZHIYAN_DS_WMS_KEY
    ZHIYAN_DS_TSDB_BACKEND / ZHIYAN_DS_TSDB_URL / ZHIYAN_DS_TSDB_TOKEN

某租户 T（多租户覆写，P2-2）：
    ZHIYAN_DS_<T>_MES_URL  （T 大写）

API 注入（P2-2）：register_from_config(tenant_id, kind, config_dict) 从请求体动态注册。

韧性：未配置的连接器不注册；registry 查询永远不抛异常。
"""

import logging
import os

from src.runtime.data_sources.registry import registry
from src.runtime.data_sources.connectors.domain import (
    MESConnector,
    ERPConnector,
    PLMConnector,
    WMSConnector,
)
from src.runtime.data_sources.timeseries.tsdb import TimeSeriesDB

logger = logging.getLogger(__name__)

_DOMAIN = {
    "mes": MESConnector,
    "erp": ERPConnector,
    "plm": PLMConnector,
    "wms": WMSConnector,
}


def _env(prefix: str, key: str, default: str = "") -> str:
    return os.getenv(f"{prefix}{key}", default)


def load_sources_for_tenant(tenant_id: str = "default") -> None:
    """从环境变量装载某租户的数据源并注册（幂等，重复调用覆盖）。"""
    pfx = "ZHIYAN_DS_" if tenant_id == "default" else f"ZHIYAN_DS_{tenant_id.upper()}_"

    for kind, cls in _DOMAIN.items():
        url = _env(pfx, f"{kind.upper()}_URL")
        key = _env(pfx, f"{kind.upper()}_KEY")
        if url:
            registry.register(cls(base_url=url, api_key=key, tenant_id=tenant_id))

    ts_backend = _env(pfx, "TSDB_BACKEND", "memory")
    ts_url = _env(pfx, "TSDB_URL")
    ts_token = _env(pfx, "TSDB_TOKEN")
    if ts_backend != "memory" or ts_url:
        registry.register(TimeSeriesDB(backend=ts_backend, url=ts_url, token=ts_token, tenant_id=tenant_id))
    else:
        # 默认注册一个内存 TSDB：始终可用，供演示/历史缓冲（断链前也有序列可查）
        registry.register(TimeSeriesDB(backend="memory", tenant_id=tenant_id))


def load_default_sources() -> None:
    """装载默认租户数据源（lifespan 调用）。"""
    load_sources_for_tenant("default")


def build_connector(kind: str, config: dict, tenant_id: str = "default") -> object | None:
    """从配置字典构建一个连接器实例（API 注入用）。"""
    kind = (kind or "").lower()
    if kind in _DOMAIN:
        return _DOMAIN[kind](
            base_url=config.get("base_url", ""),
            api_key=config.get("api_key", ""),
            tenant_id=tenant_id,
        )
    if kind == "timeseries":
        return TimeSeriesDB(
            backend=config.get("backend", "memory"),
            url=config.get("url", ""),
            token=config.get("token", ""),
            tenant_id=tenant_id,
        )
    logger.warning(f"⚠️ 未知数据源类型：{kind}")
    return None


def register_from_config(tenant_id: str, kind: str, config: dict) -> object | None:
    """从 API 请求体动态注册一个数据源。返回注册的实例或 None。"""
    src = build_connector(kind, config, tenant_id)
    if src is not None:
        registry.register(src)
        logger.info(f"📥 API 注入数据源 {tenant_id}:{kind}")
    return src
