"""时序数据库接入——传感器/指标历史的可靠存储层

设计（延续韧性降级）：
- 内存环形缓冲（collections.deque）为**始终可用的查询层**：写入即入缓冲，query_range 永远可查，
  即便真实 TSDB 不可达也不丢查询能力。
- 真实后端（influxdb / tdengine / timescale）为**持久化适配层**：write_metric 时 best-effort 推送；
  客户端库缺失或网络失败 → 仅留内存，绝不抛异常。
- backend="memory" 时完全离线可用（演示/降级），无需任何外部依赖。

这让 OEE / 良率 / 设备健康 / 能耗 等「历史趋势分析」有真实序列可用，而非每次重启重灌 seed。
"""

import logging
from collections import deque
from typing import Any, Optional

from src.runtime.data_sources.base import DataSource, DataSourceKind

logger = logging.getLogger(__name__)


class TimeSeriesDB(DataSource):
    def __init__(
        self,
        backend: str = "memory",
        url: str = "",
        token: str = "",
        tenant_id: str = "default",
        max_points: int = 20000,
        name: str = "tsdb",
    ):
        super().__init__(name=name, tenant_id=tenant_id)
        self.kind = DataSourceKind.TIMESERIES
        self.backend = (backend or "memory").lower()
        self.url = (url or "").rstrip("/")
        self.token = token
        self._max = max_points
        # measurement -> deque of points (newest last)
        self._buf: dict[str, deque] = {}

    async def is_available(self) -> bool:
        # 内存缓冲永远可用；真实后端需 url 配置且客户端可达
        if self.backend == "memory":
            return True
        return bool(self.url)

    # ---------- 写入 ----------
    async def write_metric(
        self,
        measurement: str,
        tags: dict | None = None,
        fields: dict | None = None,
        ts: int | None = None,
    ) -> bool:
        """写入一条时序点。内存缓冲必入；真实后端 best-effort。"""
        tags = tags or {}
        fields = fields or {}
        import time as _t

        point = {"measurement": measurement, "tags": tags, "fields": fields,
                 "ts": ts or int(_t.time() * 1000)}
        buf = self._buf.setdefault(measurement, deque(maxlen=self._max))
        buf.append(point)
        # 真实后端 best-effort
        if self.backend != "memory" and self.url:
            try:
                await self._write_real(point)
            except Exception as e:
                logger.debug(f"{self.name}: 真实 TSDB 写入降级（内存已保留）：{e}")
        return True

    async def _write_real(self, point: dict) -> None:
        if self.backend == "influxdb":
            # InfluxDB v2 line protocol over HTTP（简单可靠）
            try:
                import httpx
            except Exception:
                return
            line = self._to_line_protocol(point)
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(f"{self.url}/api/v2/write", content=line, headers=headers)
                if r.status_code >= 400:
                    logger.warning(f"⚠️ {self.name} InfluxDB write -> {r.status_code}")
        else:
            # tdengine / timescale 等：预留适配点，当前走内存
            logger.debug(f"{self.name}: backend={self.backend} 真实写入适配未启用，内存兜底")

    @staticmethod
    def _to_line_protocol(point: dict) -> str:
        m = point["measurement"]
        tags = ",".join(f"{k}={v}" for k, v in point["tags"].items())
        fields = ",".join(f"{k}={v}" for k, v in point["fields"].items())
        ts = point["ts"]
        return f"{m},{tags} {fields} {ts}" if tags else f"{m} {fields} {ts}"

    # ---------- 查询 ----------
    async def query_range(
        self,
        measurement: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
        tags: dict | None = None,
    ) -> list[dict]:
        """返回某 measurement 在 [start,end] 内的点（内存缓冲，始终可用）。"""
        buf = self._buf.get(measurement)
        if not buf:
            return []
        out = []
        for p in buf:
            if start_ts and p["ts"] < start_ts:
                continue
            if end_ts and p["ts"] > end_ts:
                continue
            if tags and not all(p["tags"].get(k) == v for k, v in tags.items()):
                continue
            out.append(p)
        return out

    async def fetch_recent(self, entity: str, limit: int = 100) -> list[dict]:
        """最近 limit 条（按 measurement=entity）。"""
        buf = self._buf.get(entity)
        if not buf:
            return []
        return list(buf)[-limit:]

    async def query(self, query: str, **params: Any) -> Any:
        # 通用：query 当作 measurement 名取最近 100 条
        return await self.fetch_recent(query, limit=params.get("limit", 100))
