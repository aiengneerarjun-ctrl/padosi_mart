import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ReturnItemOut(BaseModel):
    name: str
    quantity: int
    selling_unit: str


class ReturnOut(BaseModel):
    """Fail hui delivery ka ek dukaan-hissa: saaman dukaan ko wapas milna baaki hai ya mil gaya."""

    store_order_id: uuid.UUID  # confirm isi par hota hai
    order_id: uuid.UUID
    order_number: str
    store_id: uuid.UUID
    store_name: str
    status: str  # PENDING / RECEIVED
    was_picked_up: bool  # True = partner dukaan se utha chuka tha
    fail_reason: str | None
    items: list[ReturnItemOut]  # sirf wo items jo order me bache the (seller ke hataye hue nahi)
    restocked: bool
    received_at: datetime | None
    received_role: str | None
    note: str | None
    created_at: datetime


class ReceiveBody(BaseModel):
    """Dukaan: saaman wapas mil gaya. stock_ok=False = saaman kharab / bikne layak nahi, stock mat badhao."""

    stock_ok: bool = True
    note: str | None = Field(default=None, max_length=300)

    @field_validator("note")
    @classmethod
    def _clean(cls, v):
        return (v or "").strip() or None


class AdminReceiveBody(BaseModel):
    """Admin dukaan ki jagah confirm karta hai (seller jawab nahi de raha / account suspended). Karan likhna zaroori."""

    stock_ok: bool = True
    note: str = Field(min_length=3, max_length=300)