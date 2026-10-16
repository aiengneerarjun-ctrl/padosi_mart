import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Coupon(Base):
    """Admin ka banaya coupon. Discount ka niyam yahin hai; order par jo discount laga wo order me copy (snapshot) hota hai.
    Niyam wale columns (type, value, funded_by...) banne ke baad badalte nahi: badalna ho to naya coupon banao."""

    __tablename__ = "coupons"
    __table_args__ = (
        UniqueConstraint("code", name="uq_coupons_code"),
        CheckConstraint("code = upper(code) AND char_length(code) >= 3", name="ck_coupons_code"),
        CheckConstraint("discount_type IN ('FLAT','PERCENT','FREE_DELIVERY')", name="ck_coupons_type"),
        CheckConstraint("funded_by IN ('PLATFORM','SELLER')", name="ck_coupons_funded_by"),
        CheckConstraint("funded_by = 'PLATFORM' OR seller_id IS NOT NULL", name="ck_coupons_seller_funded"),
        CheckConstraint("discount_type <> 'FREE_DELIVERY' OR funded_by = 'PLATFORM'", name="ck_coupons_free_delivery_platform"),
        CheckConstraint(
            "(discount_type = 'FLAT' AND value > 0) OR (discount_type = 'PERCENT' AND value > 0 AND value <= 100) "
            "OR (discount_type = 'FREE_DELIVERY' AND value = 0)",
            name="ck_coupons_value",
        ),
        CheckConstraint("max_discount IS NULL OR (discount_type = 'PERCENT' AND max_discount > 0)", name="ck_coupons_max_discount"),
        CheckConstraint("min_order_amount >= 0", name="ck_coupons_min_order"),
        CheckConstraint("per_user_limit >= 1 AND (total_limit IS NULL OR total_limit >= 1)", name="ck_coupons_limits"),
        CheckConstraint("expires_at > starts_at", name="ck_coupons_dates"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    title_hi: Mapped[str | None] = mapped_column(String(120))
    title_bho: Mapped[str | None] = mapped_column(String(120))
    discount_type: Mapped[str] = mapped_column(String(15))  # FLAT / PERCENT / FREE_DELIVERY
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    funded_by: Mapped[str] = mapped_column(String(10), default="PLATFORM", server_default="PLATFORM")  # PLATFORM / SELLER
    seller_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sellers.id"))  # khali = sab dukaanon par
    first_order_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    total_limit: Mapped[int | None] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CouponRedemption(Base):
    """Coupon kis order par lagaya. Order cancel ho to released_at lagta hai (coupon ki ginti se hat jaata hai)."""

    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_coupon_redemptions_order"),
        CheckConstraint("discount_amount > 0", name="ck_coupon_redemptions_amount"),
        Index("ix_coupon_redemptions_coupon_user", "coupon_id", "user_id", postgresql_where=text("released_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coupon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coupons.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
