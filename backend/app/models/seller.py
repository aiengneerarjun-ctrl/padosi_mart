import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SellerType(StrEnum):
    KIRANA = "KIRANA"          # kirana / grocery (product-first)
    RESTAURANT = "RESTAURANT"  # restaurant / food (identity-first)


class SellerStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class ShopStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Seller(Base):
    """Seller ka ACCOUNT. Shop OPEN/CLOSED alag cheez hai (Store table me)."""

    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    seller_type: Mapped[str] = mapped_column(String(20))
    business_name: Mapped[str] = mapped_column(String(150))
    owner_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default=SellerStatus.PENDING, server_default="PENDING", index=True)
    status_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Store(Base):
    """Dukaan / restaurant. Aage products isi se jude honge (har product/food item ka store_id)."""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sellers.id"), index=True)
    store_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(500))
    cuisine: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    delivery_radius_km: Mapped[float] = mapped_column(Numeric(4, 1), default=3, server_default="3")
    min_order_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    shop_status: Mapped[str] = mapped_column(String(10), default=ShopStatus.CLOSED, server_default="CLOSED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())