"""能耗实时孪生体——网关/外部实时流经 twin_feed 汇入的 MACHINE holon 镜像

全息孪生社会责任：每个 DataSource 同时是某类 holon 的「孪生体状态接收端」。
本类专供 energy_carbon agent 消费：
- 网关读到的 OPC-UA / MQTT / Modbus 能耗点，经 gateway.read() → publish_to_twin_feed
  → registry.route_event("machine", {...}) 上行，汇入本孪生体的 twin_state。
- agent 推理时经 BaseAgent.twin_context() 读取这份「活镜像」，融合实时能耗/功率/绿电比。

契约（扁平 tag 约定，详见 docs/PRODUCT_DEVELOPMENT_PLAN.md §3）：
    energy_kwh__<line_id> / power_kw__<line_id> / green_ratio__<line_id>

韧性：继承 DataSource 默认 ingest（异常静默），自身只读、绝不发起业务动作（事实锚点）。
"""

from src.runtime.data_sources.base import DataSource, DataSourceKind, HolonKind


class EnergyTwinDataSource(DataSource):
    """网关实时能耗孪生体（MACHINE holon）。

    由网关/外部实时流经 registry.route_event("machine", {...}) 上行填充，
    energy_carbon agent 经 twin_context() 读取这份活镜像，融合实时能耗/功率/绿电比，
    产出含 real_time_* 字段的实时孪生结论。
    """

    kind = DataSourceKind.TIMESERIES
    name = "energy_twin"
    holon_kind = HolonKind.MACHINE
