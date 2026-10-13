import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VehicleType(StrEnum):
    BICYCLE = "BICYCLE"
    BIKE = "BIKE"
    SCOOTER = "SCOOTER"


class KycIdType(StrEnum):
    AADHAAR = "AADHAAR"
    PAN = "PAN"


class PartnerStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class DeliveryPartner(Base):
    """Delivery partner ka account + KYC. Phone users.phone me hai (OTP login wala), yahan dobara nahi.
    ID / licence ki sirf PRIVATE storage key rakhte hain; Aadhaar/PAN ka number hum store nahi karte."""

    __tablename__ = "delivery_partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    vehicle_type: Mapped[str] = mapped_column(String(10))
    vehicle_number: Mapped[str | None] = mapped_column(String(12))
    id_type: Mapped[str] = mapped_column(String(10))
    id_photo_key: Mapped[str] = mapped_column(String(255))
    licence_photo_key: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default=PartnerStatus.PENDING, server_default="PENDING", index=True)
    status_reason: Mapped[str | None] = mapped_column(String(500))
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cash_limit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("3000.00"), server_default="3000.00")  # admin tay karta hai
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DeliveryStatus(StrEnum):
    ASSIGNED = "ASSIGNED"  # partner ne order accept kiya, abhi dukaan se uthana baaki
    PICKED_UP = "PICKED_UP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    RELEASED = "RELEASED"  # pickup se pehle partner ne (ya admin suspend ne) chhod diya; order wapas free
    FAILED = "FAILED"


class Delivery(Base):
    """Ek order ki delivery ek partner ke paas (ek order = ek delivery, kai dukaanon se pickup ho sakta hai).
    Chhodi hui (RELEASED) delivery ki row history ke liye rehti hai; order dobara kisi aur ko mil sakta hai."""

    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_partners.id"))
    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.ASSIGNED, server_default="ASSIGNED")
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(200))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fail_reason: Mapped[str | None] = mapped_column(String(300))
    cod_collected: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # COD me partner ne customer se jitna cash liya
    earning: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # delivery poori hone par partner ki kamai (us waqt ka rate)
    otp_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    otp_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    

class CodDeposit(Base):
    """COD cash ka bahi-khaata: partner ne admin ko cash jama kiya (amount > 0) ya galti sudhaar (amount < 0, note zaroori).
    Rows kabhi badli / hataayi nahi jaati (database trigger). Partner ke paas cash = sum(deliveries.cod_collected) - sum(amount)."""

    __tablename__ = "cod_deposits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_partners.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None] = mapped_column(String(300))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ReturnStatus(StrEnum):
    PENDING = "PENDING"  # saaman abhi dukaan tak nahi pahunchaa / dukaan ne confirm nahi kiya
    RECEIVED = "RECEIVED"  # dukaan ne maan liya ki saaman wapas mil gaya


class StoreOrderReturn(Base):
    """Fail hui delivery ke har dukaan-hisse ka saaman dukaan ko wapas milne ka record.
    Seller (ya admin) "saaman mil gaya" confirm karta hai; tab (kirana me, saaman theek ho to) stock wapas judta hai.
    Stock ka asli hisaab inventory_transactions (reason RETURN) me rehta hai."""

    __tablename__ = "store_order_returns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    store_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store_orders.id"), unique=True)
    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("deliveries.id"))
    status: Mapped[str] = mapped_column(String(10), default=ReturnStatus.PENDING, server_default="PENDING")
    was_picked_up: Mapped[bool] = mapped_column(Boolean)
    restocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    received_role: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeliveryPaySettings(Base):
    """Partner ki kamai ka rate. Sirf ek row (id = 1), Super Admin badalta hai. Rate delivery poori hote hi us delivery par fix ho jaata hai."""

    __tablename__ = "delivery_pay_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    normal_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default="0.00")
    free_delivery_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), server_default="0.00")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PartnerPayout(Base):
    """Kamai ka bahi-khaata: admin ne partner ko paisa diya (amount > 0) ya galti sudhaar (amount < 0, note zaroori).
    Rows kabhi badli / hataayi nahi jaati (database trigger). Partner ko dena baaki = sum(deliveries.earning) - sum(amount)."""

    __tablename__ = "partner_payouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_partners.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None] = mapped_column(String(300))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())