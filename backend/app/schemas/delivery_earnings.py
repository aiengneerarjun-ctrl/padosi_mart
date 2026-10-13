import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class EarningOut(BaseModel):
    order_id: uuid.UUID
    order_number: str
    amount: float
    delivered_at: datetime


class PayoutOut(BaseModel):
    id: uuid.UUID
    amount: float  # + = admin ne paisa diya, - = galti sudhaar
    note: str | None
    created_at: datetime


class EarningsSummaryOut(BaseModel):
    total_earned: float  # kul kamai (DELIVERED deliveries ka jod)
    total_paid: float  # admin se mila hua kul paisa (sudhaar ke baad)
    due: float  # abhi admin se milna baaki = earned - paid
    recent_earnings: list[EarningOut]
    recent_payouts: list[PayoutOut]


class AdminEarningsRowOut(BaseModel):
    partner_id: uuid.UUID
    full_name: str
    phone: str
    status: str
    total_earned: float
    total_paid: float
    due: float


class PayoutBody(BaseModel):
    """amount > 0: admin ne partner ko paisa diya. amount < 0: pehle ki galti sudhaar (note zaroori)."""

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


class RatesOut(BaseModel):
    normal_rate: float  # customer ne delivery fee diya
    free_delivery_rate: float  # customer ka delivery fee 0 (free-delivery order)
    updated_at: datetime


class RateBody(BaseModel):
    """Admin partner ki kamai ka rate badalta hai. Jo bheja wahi badalta hai (kam se kam ek). Karan zaroori; audit log me jaata hai.
    Naya rate sirf aage ki deliveries par lagta hai, purani deliveries ka paisa nahi badalta."""

    normal_rate: Decimal | None = Field(default=None, ge=0, le=10000, max_digits=10, decimal_places=2)
    free_delivery_rate: Decimal | None = Field(default=None, ge=0, le=10000, max_digits=10, decimal_places=2)
    reason: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def _check(self):
        if self.normal_rate is None and self.free_delivery_rate is None:
            raise ValueError("kam se kam ek rate bhejo")
        return self