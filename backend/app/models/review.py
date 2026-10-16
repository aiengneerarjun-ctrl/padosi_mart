import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Review(Base):
    """Delivery ke baad customer ka review: dukaan ka ya delivery partner ka. Rating / comment banne ke baad badalte nahi.
    Admin sirf chhupa sakta hai (status HIDDEN, karan ke saath); chhupa hua review kisi ko dikhta nahi aur average me nahi ginta."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        CheckConstraint("status IN ('VISIBLE','HIDDEN')", name="ck_reviews_status"),
        CheckConstraint(
            "(target_type = 'STORE' AND store_id IS NOT NULL AND seller_id IS NOT NULL AND partner_id IS NULL) OR "
            "(target_type = 'PARTNER' AND partner_id IS NOT NULL AND store_id IS NULL AND seller_id IS NULL)",
            name="ck_reviews_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    target_type: Mapped[str] = mapped_column(String(10))  # STORE / PARTNER
    store_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stores.id"))
    seller_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sellers.id"))
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("delivery_partners.id"))
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="VISIBLE", server_default="VISIBLE")
    hidden_reason: Mapped[str | None] = mapped_column(String(300))
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RatingSummary(Base):
    """Dukaan / partner ke star ki ginti (sirf VISIBLE reviews). Average yahin se nikalta hai."""

    __tablename__ = "rating_summaries"
    __table_args__ = (
        PrimaryKeyConstraint("target_type", "target_id"),
        CheckConstraint("target_type IN ('STORE','PARTNER')", name="ck_rating_summaries_type"),
        CheckConstraint("star1 >= 0 AND star2 >= 0 AND star3 >= 0 AND star4 >= 0 AND star5 >= 0", name="ck_rating_summaries_nonneg"),
    )

    target_type: Mapped[str] = mapped_column(String(10))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    star1: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    star2: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    star3: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    star4: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    star5: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
