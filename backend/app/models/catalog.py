import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProductStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"  # admin approve karne tak customer ko nahi dikhega
    ACTIVE = "ACTIVE"
    OUT_OF_STOCK = "OUT_OF_STOCK"  # stock 0 hote hi apne aap
    INACTIVE = "INACTIVE"  # seller ne khud chhupaya
    REJECTED = "REJECTED"


class StockReason(StrEnum):
    INITIAL = "INITIAL"
    STOCK_IN = "STOCK_IN"
    ADJUSTMENT = "ADJUSTMENT"
    DAMAGED = "DAMAGED"
    ORDER = "ORDER"  # aage order step me use hoga
    ORDER_CANCEL = "ORDER_CANCEL"
    RETURN = "RETURN"


class Category(Base):
    """Category / sub-category. parent_id khali = main category. Sirf 2 level."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))  # English (default)
    name_hi: Mapped[str | None] = mapped_column(String(100))
    name_bho: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    """Product / food item. Hamesha ek store se juda (store_id), restaurant ho ya kirana."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("store_id", "sku", name="uq_products_store_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id"))
    sku: Mapped[str] = mapped_column(String(64))
    barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200))  # English (default)
    name_hi: Mapped[str | None] = mapped_column(String(200))
    name_bho: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    selling_unit: Mapped[str] = mapped_column(String(50))  # "1 kg", "500 ml", "6 pcs"
    mrp: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(
        String(20), default=ProductStatus.PENDING_APPROVAL, server_default="PENDING_APPROVAL", index=True
    )
    status_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    inventory: Mapped["Inventory"] = relationship(lazy="joined", uselist=False)
    images: Mapped[list["ProductImage"]] = relationship(lazy="selectin", order_by="ProductImage.position")


class Inventory(Base):
    """Product ka current stock. Quantity kabhi 0 se neeche nahi jaa sakti (DB constraint bhi hai)."""

    __tablename__ = "inventory"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InventoryTransaction(Base):
    """Stock ka har badlav yahan likha jaata hai. Purani rows badli nahi jaati, sirf nayi judti hain."""

    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    change: Mapped[int] = mapped_column(Integer)  # +10 stock aaya, -2 kam hua
    quantity_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(300))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
class ProductImage(Base):
    """Product ki photo. position 0 = primary (listing me yahi dikhti hai). Photo object storage me rehti hai."""

    __tablename__ = "product_images"
    # deferrable: reorder/delete me positions ek saath badalte hain, check commit par hota hai
    __table_args__ = (
        UniqueConstraint("product_id", "position", name="uq_product_images_position", deferrable=True, initially="DEFERRED"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    key_prefix: Mapped[str] = mapped_column(String(200))  # products/<product_id>/<image_id>
    sha256: Mapped[str] = mapped_column(String(64))  # duplicate photo pakadne ke liye
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())