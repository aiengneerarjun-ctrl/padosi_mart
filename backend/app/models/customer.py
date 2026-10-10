import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MAX_ADDRESSES = 10  # ek customer ke zyada se zyada active address


class CustomerAddress(Base):
    """Customer ka delivery address. Delete = soft delete (is_active false), kyunki purane orders isse jude honge."""

    __tablename__ = "customer_addresses"
    __table_args__ = (
        CheckConstraint("label IN ('HOME','WORK','OTHER')", name="ck_customer_addresses_label"),
        CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180", name="ck_customer_addresses_geo"),
        # Ek customer ka sirf ek active default address ho sakta hai
        Index("uq_customer_one_default_address", "user_id", unique=True, postgresql_where=text("is_default AND is_active")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(10), default="HOME", server_default="HOME")
    receiver_name: Mapped[str] = mapped_column(String(100))
    receiver_phone: Mapped[str] = mapped_column(String(15))
    address_line: Mapped[str] = mapped_column(String(300))
    landmark: Mapped[str | None] = mapped_column(String(150))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FavouriteStore(Base):
    """Customer ki pasandida dukaan. (user_id, store_id) primary key hai, isliye dobara add karna safe hai."""

    __tablename__ = "favourite_stores"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FavouriteProduct(Base):
    __tablename__ = "favourite_products"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())