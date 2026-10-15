import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentSessionOut(BaseModel):
    """App ke Cashfree SDK ko ye chahiye: payment_session_id + provider_order_id + environment."""

    order_id: uuid.UUID
    provider_order_id: str  # Cashfree me is order ka id
    payment_session_id: str
    amount: float
    environment: str  # "sandbox" ya "production" (SDK ko yahi batana hota hai)
    expires_at: datetime  # isse pehle payment poori karni hai, warna order cancel


class RefundOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    refund_id: str
    amount: float
    status: str  # PENDING / SUCCESS / FAILED
    reason_code: str  # ORDER_CANCELLED / ITEMS_REMOVED / LATE_PAYMENT / ADMIN
    note: str | None
    cf_refund_id: str | None
    provider_status: str | None
    created_at: datetime
    updated_at: datetime


class PaymentDetailOut(BaseModel):
    order_id: uuid.UUID
    order_number: str
    provider_order_id: str
    amount: float
    status: str  # CREATED / PAID
    cf_payment_id: str | None
    paid_at: datetime | None
    refunded_total: float  # PENDING + SUCCESS refunds
    refundable: float  # abhi aur kitna wapas kiya ja sakta hai
    refunds: list[RefundOut]


class AdminRefundBody(BaseModel):
    """Admin kisi paid order ka paisa (poora ya hissa) wapas karta hai, jaise fail hui delivery me. Karan zaroori."""

    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    note: str = Field(min_length=3, max_length=300)


class ExpiredOut(BaseModel):
    expired: int  # kitne bina-payment wale orders cancel hue