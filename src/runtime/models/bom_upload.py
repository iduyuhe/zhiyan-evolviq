"""BOM 上传记录（S2-5，#311）——信任爬梯③「上传 1 份文件」的落盘载体

总纲 §3.5 中圈语义：外部信号 × 轻量内部数据（上传 1 文件即达信任爬梯③）。
BOM 明细以 JSON Text 存储（轻量内部数据，不建明细表——爬梯③阶段企业
尚未接系统，文件级粒度足够；接网关后自然升级为实时数据源）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base, TimestampMixin


class BomUpload(Base, TimestampMixin):
    __tablename__ = "bom_uploads"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 物料成本合计（qty × unit_price 求和，单位：元）
    total_material_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 明细 JSON：[{material, qty, unit_price, cost}]
    items_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    def to_dict(self, with_items: bool = False) -> dict:
        import json

        out = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "filename": self.filename,
            "product_name": self.product_name,
            "item_count": self.item_count,
            "total_material_cost": self.total_material_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if with_items:
            try:
                out["items"] = json.loads(self.items_json or "[]")
            except Exception:
                out["items"] = []
        return out
