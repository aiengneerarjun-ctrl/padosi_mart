import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Payment(Base):
    """Ek ONLINE order ka Cashfree payment. Ek order par ek hi row (customer usi par kai baar koshish kar sakta hai)."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        CheckConstraint("status IN ('CREATED', 'PAID')", name="ck_payments_status"),
        CheckConstraint("(status = 'PAID') = (paid_at IS NOT NULL)", name="ck_payments_paid_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    provider: Mapped[str] = mapped_column(String(20), default="CASHFREE", server_default="CASHFREE")
    provider_order_id: Mapped[str] = mapped_column(String(45), unique=True)  # Cashfree me hamara order_id
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(10), default="CREATED", server_default="CREATED")  # CREATED / PAID
    cf_order_id: Mapped[str | None] = mapped_column(String(40))
    cf_payment_id: Mapped[str | None] = mapped_column(String(40))
    payment_session_id: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Refund(Base):
    """Customer ko paisa wapas (poora ya hissa). Cashfree ko bhejne ka kaam payment service karti hai; status yahan rehta hai."""

    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_refunds_amount"),
        CheckConstraint("status IN ('PENDING', 'SUCCESS', 'FAILED')", name="ck_refunds_status"),
        Index("ix_refunds_order", "order_id"),
        Index("ix_refunds_status", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"))
    refund_id: Mapped[str] = mapped_column(String(40), unique=True)  # Cashfree me hamara refund_id
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(10), default="PENDING", server_default="PENDING")  # PENDING / SUCCESS / FAILED
    reason_code: Mapped[str] = mapped_column(String(30))  # ORDER_CANCELLED / ITEMS_REMOVED / LATE_PAYMENT / ADMIN
    note: Mapped[str | None] = mapped_column(String(300))
    cf_refund_id: Mapped[str | None] = mapped_column(String(40))
    provider_status: Mapped[str | None] = mapped_column(String(30))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaymentEvent(Base):
    """Cashfree se aaya webhook (ek baar hi chalta hai: event_key unique)."""

    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_key: Mapped[str] = mapped_column(String(160), unique=True)
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())