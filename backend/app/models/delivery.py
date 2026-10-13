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
    cod_collected: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # COD me partner ne customer se jitna cash liya
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