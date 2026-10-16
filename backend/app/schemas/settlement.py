import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class SettlementOrderOut(BaseModel):
    order_id: uuid.UUID
    order_number: str
    store_name: str
    items_subtotal: float  # hataye gaye items ke baad ki bikri
    commission_rate: float  # percent, us waqt ka
    commission_amount: float
    seller_discount: float = 0.0  # seller-funded coupon me seller ka hissa
    net: float  # seller ko milega = items_subtotal - commission_amount - seller_discount
    delivered_at: datetime


class SellerPayoutOut(BaseModel):
    id: uuid.UUID
    amount: float  # + = admin ne paisa diya, - = galti sudhaar
    note: str | None
    created_at: datetime


class SettlementSummaryOut(BaseModel):
    total_sales: float  # deliver hue orders ki kul bikri (hataye gaye items ke baad)
    total_commission: float
    total_seller_discount: float = 0.0  # seller-funded coupons me seller ka kul hissa
    total_earned: float  # = bikri - commission - seller_discount
    total_paid: float  # admin se mila hua kul paisa (sudhaar ke baad)
    due: float  # abhi admin se milna baaki = earned - paid
    recent_orders: list[SettlementOrderOut]
    recent_payouts: list[SellerPayoutOut]


class AdminSettlementRowOut(BaseModel):
    seller_id: uuid.UUID
    business_name: str
    phone: str
    status: str
    total_sales: float
    total_commission: float
    total_seller_discount: float = 0.0
    total_earned: float
    total_paid: float
    due: float


class SettlementRatesOut(BaseModel):
    kirana_rate: float  # percent
    restaurant_rate: float  # percent
    updated_at: datetime


class SettlementRateBody(BaseModel):
    """Admin commission (percent) badalta hai. Jo bheja wahi badalta hai (kam se kam ek). Karan zaroori; audit log me jaata hai.
    Naya rate sirf aage ki deliveries par lagta hai, purane hisaab nahi badalte."""

    kirana_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    restaurant_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    reason: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def _check(self):
        if self.kirana_rate is None and self.restaurant_rate is None:
            raise ValueError("kam se kam ek rate bhejo")
        return self


class SellerPayoutBody(BaseModel):
    """amount > 0: admin ne seller ko paisa diya. amount < 0: pehle ki galti sudhaar (note zaroori)."""

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