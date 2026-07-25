"""DataSource 抽象——所有生产数据入口的统一契约

设计要点（延续全局韧性降级铁律）：
- DataSource 是 agent 取数的统一接口；seed / 网关 / MES / ERP / WMS / PLM / 时序库
  都实现它，agent tools 只依赖该契约，不再直接读 seed 文件。
- is_available()：数据源是否真正可达（配置存在 + 连通）。不可达时 agent 自动回退 seed。
- query() / fetch_recent()：语义化取数，任一失败仅返回空/None，**绝不抛异常阻断管道**。
- 事实锚点：DataSource 只「读」，绝不改写任何业务数字或动作。

多租户：每个 DataSource 带 tenant_id；注册表按租户隔离。
"""

from enum import Enum
from typing import Any, Optional


class DataSourceKind(str, Enum):
    SEED = "seed"
    MES = "mes"
    ERP = "erp"
    PLM = "plm"
    WMS = "wms"
    GATEWAY = "gateway"
    TIMESERIES = "timeseries"


class DataSource:
    """生产数据入口的统一抽象（基类，不可直接实例化语义方法）。"""

    kind: DataSourceKind = DataSourceKind.SEED
    name: str = "base"

    def __init__(self, name: str | None = None, tenant_id: str = "default"):
        self.name = name or self.__class__.__name__
        self.tenant_id = tenant_id
        self._available: bool | None = None  # 缓存 is_available 结果

    async def is_available(self) -> bool:
        """数据源是否真正可达。子类可重写探测逻辑；默认按是否配置判断。"""
        return False

    async def query(self, query: str, **params: Any) -> Any:
        """语义化查询，返回数据。失败返回 None（韧性）。"""
        raise NotImplementedError

    async def fetch_recent(self, entity: str, limit: int = 100) -> list[dict]:
        """最近记录（时序/历史）。失败返回 []（韧性）。"""
        return []

    async def health(self) -> dict:
        ok = False
        try:
            ok = await self.is_available()
        except Exception:
            ok = False
        return {"name": self.name, "kind": self.kind.value, "tenant": self.tenant_id, "available": ok}

    def _key(self) -> str:
        return f"{self.tenant_id}:{self.kind.value}:{self.name}"

    def __repr__(self) -> str:
        return f"<DataSource {self._key()}>"
