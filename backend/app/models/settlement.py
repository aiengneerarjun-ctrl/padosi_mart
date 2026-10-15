import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SettlementSettings(Base):
    """Platform ka commission (percent), dukaan ke type ke hisaab se. Sirf ek row (id = 1), Super Admin badalta hai.
    Rate delivery poori hote hi us dukaan-hisse par fix ho jaata hai (store_orders.commission_rate)."""

    __tablename__ = "settlement_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    kirana_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), server_default="0.00")
    restaurant_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), server_default="0.00")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class SellerPayout(Base):
    """Seller ke hisaab ka bahi-khaata: admin ne seller ko paisa diya (amount > 0) ya galti sudhaar (amount < 0, note zaroori).
    Rows kabhi badli / hataayi nahi jaati (database trigger). Seller ko dena baaki = kul bikri - commission - sum(amount)."""

    __tablename__ = "seller_payouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sellers.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None] = mapped_column(String(300))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())