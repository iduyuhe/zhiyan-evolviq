"""供应链核心数据模型"""

import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.runtime.models.base import Base, TimestampMixin


class BOMStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    draft = "draft"


class POStatus(str, enum.Enum):
    open = "open"
    confirmed = "confirmed"
    in_transit = "in_transit"
    received = "received"
    delayed = "delayed"
    cancelled = "cancelled"


class MaterialRisk(str, enum.Enum):
    low = "low"          # 齐套
    medium = "medium"    # 部分缺料
    high = "high"        # 严重缺料
    critical = "critical"  # 缺料停产风险


class Material(Base):
    """物料主数据"""
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(128))
    unit: Mapped[str] = mapped_column(String(16))
    standard_price: Mapped[float] = mapped_column(Float)
    supplier: Mapped[str] = mapped_column(String(256))
    lead_time_days: Mapped[int] = mapped_column(default=0)
    min_order_qty: Mapped[int] = mapped_column(default=1)


class BOM(Base, TimestampMixin):
    """物料清单（Bill of Materials）"""
    __tablename__ = "boms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_code: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str] = mapped_column(String(256))
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[BOMStatus] = mapped_column(Enum(BOMStatus), default=BOMStatus.active)
    total_qty: Mapped[int] = mapped_column(default=0)
    items: Mapped[list["BOMItem"]] = relationship(back_populates="bom", cascade="all, delete-orphan")


class BOMItem(Base):
    """BOM明细"""
    __tablename__ = "bom_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("boms.id"))
    bom: Mapped["BOM"] = relationship(back_populates="items")
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"))
    material: Mapped["Material"] = relationship()
    quantity: Mapped[int] = mapped_column(default=1)
    reference: Mapped[str] = mapped_column(String(64), default="")


class PurchaseOrder(Base, TimestampMixin):
    """采购订单"""
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"))
    material: Mapped["Material"] = relationship()
    supplier: Mapped[str] = mapped_column(String(256))
    quantity: Mapped[int] = mapped_column(default=0)
    received_qty: Mapped[int] = mapped_column(default=0)
    unit_price: Mapped[float] = mapped_column(Float)
    status: Mapped[POStatus] = mapped_column(Enum(POStatus), default=POStatus.open)
    expected_date: Mapped[datetime.date] = mapped_column()
    actual_date: Mapped[datetime.date | None] = mapped_column(nullable=True)


class Inventory(Base, TimestampMixin):
    """库存记录"""
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"), unique=True)
    material: Mapped["Material"] = relationship()
    on_hand_qty: Mapped[int] = mapped_column(default=0)
    reserved_qty: Mapped[int] = mapped_column(default=0)
    available_qty: Mapped[int] = mapped_column(default=0)
    warehouse: Mapped[str] = mapped_column(String(64), default="main")


class SupplyCheck(Base, TimestampMixin):
    """齐套检查结果"""
    __tablename__ = "supply_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("boms.id"))
    bom: Mapped["BOM"] = relationship()
    check_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    overall_risk: Mapped[MaterialRisk] = mapped_column(Enum(MaterialRisk))
    completeness_pct: Mapped[float] = mapped_column(Float)  # 齐套率
    details: Mapped[list["SupplyCheckDetail"]] = relationship(cascade="all, delete-orphan")


class SupplyCheckDetail(Base):
    """齐套检查明细"""
    __tablename__ = "supply_check_details"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supply_checks.id"))
    check: Mapped["SupplyCheck"] = relationship(back_populates="details")
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"))
    material: Mapped["Material"] = relationship()
    required_qty: Mapped[int] = mapped_column()
    available_qty: Mapped[int] = mapped_column()
    shortage_qty: Mapped[int] = mapped_column(default=0)
    risk: Mapped[MaterialRisk] = mapped_column(Enum(MaterialRisk))
    alternative_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuthorizationBoundary(Base, TimestampMixin):
    """授权边界配置——人定义Agent可自主执行的范围"""
    __tablename__ = "authorization_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(default=True)
    # 授权规则（JSON格式存储）
    rules: Mapped[str] = mapped_column(Text, default="{}")
    # 示例规则结构：
    # {
    #   "max_price_variation_pct": 5.0,
    #   "max_lock_qty_per_item": 1000,
    #   "allowed_categories": ["电阻", "电容", "IC"],
    #   "max_total_value_cny": 50000,
    #   "require_approval_for": ["新供应商", "价格波动>5%", "非标品"]
    # }
