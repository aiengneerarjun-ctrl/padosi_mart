import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FailBody(BaseModel):
    """Delivery fail hui: kyun. OTHER ho to note zaroori."""

    reason_code: Literal["CUSTOMER_UNREACHABLE", "CUSTOMER_REFUSED", "WRONG_ADDRESS", "PARTNER_ISSUE", "OTHER"]
    note: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def _check(self):
        self.note = (self.note or "").strip() or None
        if self.reason_code == "OTHER" and self.note is None:
            raise ValueError("OTHER ke liye note likhna zaroori hai")
        return self


class FailedOut(BaseModel):
    order_id: uuid.UUID
    order_number: str
    status: str  # FAILED_DELIVERY


class AdminDeliveryOut(BaseModel):
    delivery_id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    order_status: str
    partner_id: uuid.UUID
    partner_name: str
    partner_phone: str
    status: str  # delivery ka status
    assigned_at: datetime
    delivered_at: datetime | None
    failed_at: datetime | None
    fail_reason: str | None
    otp_locked: bool  # OTP ki galat koshishon se abhi band hai
    cod_collected: float | None