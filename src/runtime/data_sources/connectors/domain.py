"""MES / ERP / PLM / WMS 连接器——生产业务系统的真实数据入口

实现方式：
- 统一基于 REST（现代 MES/ERP/PLM/WMS 多暴露 OpenAPI）。base_url + api_key 由配置/环境变量注入。
- 每个连接器暴露**语义化方法**（如 mes.get_work_orders、wms.get_inventory），
  agent tools 直接调用语义方法，不必关心底层 HTTP。
- 韧性铁律：未配置 → is_available()=False（agent 自动回退 seed）；调用失败 → 返回空/None，绝不抛异常。
- 真实写入/事务（下发工单、过账）不在本阶段范围；本层聚焦「读取生产数据」。

注：SQL 直连（通过 sql_dsn）作为可选扩展点保留，默认走 REST。
"""

import logging
from typing import Any, Optional

from src.runtime.data_sources.base import DataSource, DataSourceKind, HolonKind
from src.runtime.data_sources.field_mapping import (
    DEFAULT_AUDIT_PATH,
    apply_field_map,
    parse_field_map,
)

logger = logging.getLogger(__name__)


class RestConnector(DataSource):
    """REST 型数据源基类：配置驱动 + 惰性 httpx + 韧性降级。"""

    def __init__(
        self,
        kind: DataSourceKind,
        name: str | None = None,
        base_url: str = "",
        api_key: str = "",
        tenant_id: str = "default",
        timeout: float = 5.0,
        wb_field_map: dict | str | None = None,
        wb_audit_path: str = "",
    ):
        super().__init__(name=name, tenant_id=tenant_id)
        self.kind = kind
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        # 回写审计字段映射（v28.3）：{标准字段: 目标系统字段}，默认恒等映射
        self.wb_field_map: dict[str, str] = parse_field_map(
            wb_field_map, source=f"{tenant_id}:{name or kind}"
        )
        # 审计端点路径覆写（默认 audit/records）
        self.wb_audit_path: str = (wb_audit_path or "").strip().lstrip("/") or DEFAULT_AUDIT_PATH

    async def is_available(self) -> bool:
        # 配置驱动：有 base_url 即视为可达（真实失败在调用时韧性降级）
        return bool(self.base_url)

    async def _get(self, path: str, params: dict | None = None) -> Any:
        if not self.base_url:
            return None
        try:
            import httpx
        except Exception:
            logger.debug(f"{self.name}: httpx 未安装，降级为空")
            return None
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.get(url, params=params, headers=headers)
                if r.status_code >= 400:
                    logger.warning(f"⚠️ {self.name} GET {url} -> {r.status_code}")
                    return None
                return r.json()
        except Exception as e:
            logger.warning(f"⚠️ {self.name} 取数失败（韧性降级）：{e}")
            return None

    async def query(self, query: str, **params: Any) -> Any:
        # 通用兜底：把 query 当作 REST 路径
        return await self._get(query, params)

    async def _post(self, path: str, json_body: dict) -> Any:
        """通用写方法（回写审计桥用）。失败韧性降级：返回 None，不抛异常。"""
        if not self.base_url:
            return None
        try:
            import httpx
        except Exception:
            logger.debug(f"{self.name}: httpx 未安装，写回降级")
            return None
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.post(url, json=json_body, headers=headers)
                if r.status_code >= 400:
                    logger.warning(f"⚠️ {self.name} POST {url} -> {r.status_code}")
                    return None
                return r.json() if r.content else {"ok": True}
        except Exception as e:
            logger.warning(f"⚠️ {self.name} 写回失败（韧性降级）：{e}")
            return None


class MESConnector(RestConnector):
    """制造执行系统：工单、产线进度、质量缺陷。"""
    holon_kind = HolonKind.MACHINE

    def __init__(self, base_url: str = "", api_key: str = "", tenant_id: str = "default", timeout: float = 5.0,
                 wb_field_map: dict | str | None = None, wb_audit_path: str = ""):
        super().__init__(DataSourceKind.MES, name="mes", base_url=base_url, api_key=api_key,
                         tenant_id=tenant_id, timeout=timeout,
                         wb_field_map=wb_field_map, wb_audit_path=wb_audit_path)

    async def get_work_orders(self, status: str | None = None) -> list[dict]:
        params = {"status": status} if status else None
        data = await self._get("work-orders", params)
        return data.get("items", []) if isinstance(data, dict) else (data or [])

    async def get_production_progress(self, work_order_id: str) -> dict | None:
        return await self._get(f"work-orders/{work_order_id}/progress")

    async def get_quality_defects(self, line_id: str | None = None) -> list[dict]:
        params = {"line": line_id} if line_id else None
        data = await self._get("quality/defects", params)
        return data.get("items", []) if isinstance(data, dict) else (data or [])

    async def post_audit_record(self, record: dict) -> Any:
        """回写审计记录（智衍决策/审批结论落 ERP/MES 作为审计，不推倒账本）。

        v28.3：POST 前按租户级字段映射把标准字段改名为目标 MES 的 schema；
        端点路径可覆写（默认 audit/records）。
        """
        return await self._post(self.wb_audit_path, apply_field_map(record, self.wb_field_map))


class ERPConnector(RestConnector):
    """企业资源计划：采购订单、供应商、财务。"""
    holon_kind = HolonKind.METHOD

    def __init__(self, base_url: str = "", api_key: str = "", tenant_id: str = "default", timeout: float = 5.0,
                 wb_field_map: dict | str | None = None, wb_audit_path: str = ""):
        super().__init__(DataSourceKind.ERP, name="erp", base_url=base_url, api_key=api_key,
                         tenant_id=tenant_id, timeout=timeout,
                         wb_field_map=wb_field_map, wb_audit_path=wb_audit_path)

    async def get_purchase_orders(self, status: str | None = None) -> list[dict]:
        params = {"status": status} if status else None
        data = await self._get("purchase-orders", params)
        return data.get("items", []) if isinstance(data, dict) else (data or [])

    async def get_suppliers(self, material_code: str | None = None) -> list[dict]:
        params = {"material": material_code} if material_code else None
        data = await self._get("suppliers", params)
        return data.get("items", []) if isinstance(data, dict) else (data or [])

    async def get_finance(self, period: str | None = None) -> dict | None:
        return await self._get("finance/summary", {"period": period} if period else None)

    async def post_audit_record(self, record: dict) -> Any:
        """回写审计记录（智衍决策/审批结论落 ERP 作为审计轨迹）。

        v28.3：POST 前按租户级字段映射把标准字段改名为目标 ERP 的 schema；
        端点路径可覆写（默认 audit/records）。
        """
        return await self._post(self.wb_audit_path, apply_field_map(record, self.wb_field_map))


class PLMConnector(RestConnector):
    """产品生命周期管理：零部件、BOM、文档。"""
    holon_kind = HolonKind.METHOD

    def __init__(self, base_url: str = "", api_key: str = "", tenant_id: str = "default", timeout: float = 5.0):
        super().__init__(DataSourceKind.PLM, name="plm", base_url=base_url, api_key=api_key,
                         tenant_id=tenant_id, timeout=timeout)

    async def get_parts(self, category: str | None = None) -> list[dict]:
        params = {"category": category} if category else None
        data = await self._get("parts", params)
        return data.get("items", []) if isinstance(data, dict) else (data or [])

    async def get_bom(self, part_no: str) -> dict | None:
        return await self._get(f"parts/{part_no}/bom")

    async def get_documents(self, part_no: str | None = None) -> list[dict]:
        params = {"part": part_no} if part_no else None
        data = await self._get("documents", params)
        return data.get("items", []) if isinstance(data, dict) else (data or [])


class WMSConnector(RestConnector):
    """仓储管理系统：库存、库位、出入库。"""
    holon_kind = HolonKind.MATERIAL

    def __init__(self, base_url: str = "", api_key: str = "", tenant_id: str = "default", timeout: float = 5.0):
        super().__init__(DataSourceKind.WMS, name="wms", base_url=base_url, api_key=api_key,
                         tenant_id=tenant_id, timeout=timeout)

    async def get_inventory(self, material_codes: list[str] | None = None) -> dict:
        params = {"codes": ",".join(material_codes)} if material_codes else None
        data = await self._get("inventory", params)
        # 兼容两种返回：{code: {...}} 或 {"items":[{code,...}]}
        if isinstance(data, dict):
            if "items" in data:
                return {i.get("code"): i for i in data["items"]}
            return data
        return {}

    async def get_locations(self, material_code: str) -> list[dict]:
        data = await self._get(f"inventory/{material_code}/locations")
        return data.get("items", []) if isinstance(data, dict) else (data or [])

    async def get_shipments(self, direction: str = "out") -> list[dict]:
        data = await self._get("shipments", {"direction": direction})
        return data.get("items", []) if isinstance(data, dict) else (data or [])
