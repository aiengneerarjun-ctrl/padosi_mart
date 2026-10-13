import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class CashCollectionOut(BaseModel):
    order_id: uuid.UUID
    order_number: str
    amount: float
    delivered_at: datetime


class CashDepositOut(BaseModel):
    id: uuid.UUID
    amount: float  # + = partner ne cash jama kiya, - = galti sudhaar
    note: str | None
    created_at: datetime


class CashSummaryOut(BaseModel):
    cash_collected: float  # COD me customers se liya hua kul cash
    cash_deposited: float  # admin ko jama kiya hua kul cash (sudhaar ke baad)
    cash_in_hand: float  # abhi partner ke paas = collected - deposited
    cash_limit: float  # admin ne is partner ke liye jo limit lagayi hai (default 3000)
    limit_reached: bool  # True = cash_in_hand limit tak pahunch gaya, naya order nahi milega
    recent_collections: list[CashCollectionOut]
    recent_deposits: list[CashDepositOut]


class AdminCashRowOut(BaseModel):
    partner_id: uuid.UUID
    full_name: str
    phone: str
    status: str
    cash_collected: float
    cash_deposited: float
    cash_in_hand: float
    cash_limit: float
    limit_reached: bool


class DepositBody(BaseModel):
    """amount > 0: partner ne cash jama kiya. amount < 0: pehle ki galti sudhaar (note zaroori)."""

    amount: Decimal = Field(max_digits=10, decimal_places=2)
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _check(self):
        if self.amount == 0:
            raise ValueError("amount 0 nahi ho sakta")
        self.note = (self.note or "").strip() or None
        if self.amount < 0 and self.note is None:
            raise ValueError("sudhaar ke liye note likhna zaroori hai")
        return self


class LimitBody(BaseModel):
    """Admin partner ki COD cash limit badalta hai. Karan likhna zaroori (audit log me jaata hai)."""

    cash_limit: Decimal = Field(gt=0, le=100000, max_digits=10, decimal_places=2)
    reason: str = Field(min_length=3, max_length=300)