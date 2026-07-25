"""DataSource 抽象——统一取数契约 + 孪生体状态上行（twin_feed）

设计要点（延续全局韧性降级铁律）：
- DataSource 是 agent 取数的统一接口；seed / 网关 / MES / ERP / WMS / PLM / 时序库
  都实现它，agent tools 只依赖该契约，不再直接读 seed 文件。
- 全息孪生社会语义：每个 DataSource 同时是某类 holon（人/机/料/法/环）的**孪生体
  状态接收端（twin_feed）**——实时网关流经 registry.route_event() 汇入其 twin_state，
  agent 推理时可读取这份"活镜像"；自身仍是「只读」契约（事实锚点：只接收状态上行、
  绝不发起任何业务动作或改写业务数字）。
- is_available()：数据源是否真正可达（配置存在 + 连通）。不可达时 agent 自动回退 seed。
- query() / fetch_recent()：语义化取数，任一失败仅返回空/None，**绝不抛异常阻断管道**。

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


class HolonKind(str, Enum):
    """全息孪生社会中的 holon 分类（5M + 未知）。用于孪生体状态路由。"""

    HUMAN = "human"
    MACHINE = "machine"
    MATERIAL = "material"
    METHOD = "method"
    ENV = "env"
    UNKNOWN = "unknown"


class DataSource:
    """生产数据入口的统一抽象（基类，不可直接实例化语义方法）。

    每个实例对应某类 holon 的孪生体：twin_state 缓存实时上行状态，agent 推理读取。
    """

    kind: DataSourceKind = DataSourceKind.SEED
    name: str = "base"
    holon_kind: HolonKind = HolonKind.MACHINE  # 子类按 5M 覆盖

    def __init__(self, name: str | None = None, tenant_id: str = "default"):
        self.name = name or self.__class__.__name__
        self.tenant_id = tenant_id
        self._available: bool | None = None  # 缓存 is_available 结果
        # 孪生体状态快照：实时上行汇此处，agent 推理读取
        self.twin_state: dict = {"values": {}, "updated_at": None, "source": None}

    # ---- 孪生体状态上行（twin_feed）----
    def ingest(self, values: dict, source: str | None = None) -> None:
        """接收实时状态上行，更新孪生体快照。韧性：异常静默吞掉，不阻断管道。"""
        try:
            import time
            self.twin_state["values"].update(values or {})
            self.twin_state["updated_at"] = time.time()
            self.twin_state["source"] = source
        except Exception:
            pass

    def get_twin_state(self) -> dict:
        """返回孪生体最新状态（values + 时间戳 + 来源）。"""
        return self.twin_state

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
        return {
            "name": self.name,
            "kind": self.kind.value,
            "holon": self.holon_kind.value,
            "tenant": self.tenant_id,
            "available": ok,
            "twin_updated_at": self.twin_state.get("updated_at"),
        }

    def _key(self) -> str:
        return f"{self.tenant_id}:{self.kind.value}:{self.name}"

    def __repr__(self) -> str:
        return f"<DataSource {self._key()} holon={self.holon_kind.value}>"
