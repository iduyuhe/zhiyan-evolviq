"""数据接入层（P1）入口

统一总线：seed / 网关 / MES / ERP / PLM / WMS / 时序库 都实现 DataSource 契约，
agent tools 只依赖 registry.get(kind)，自动 seed→live 切换。P2 图谱闭环与多租户配置均挂在 registry 上。
"""

from src.runtime.data_sources.base import DataSource, DataSourceKind
from src.runtime.data_sources.registry import DataSourceRegistry, registry
from src.runtime.data_sources.connectors.domain import (
    MESConnector,
    ERPConnector,
    PLMConnector,
    WMSConnector,
)
from src.runtime.data_sources.timeseries.tsdb import TimeSeriesDB

__all__ = [
    "DataSource",
    "DataSourceKind",
    "DataSourceRegistry",
    "registry",
    "MESConnector",
    "ERPConnector",
    "PLMConnector",
    "WMSConnector",
    "TimeSeriesDB",
]
