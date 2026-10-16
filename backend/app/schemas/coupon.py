import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

DiscountType = Literal["FLAT", "PERCENT", "FREE_DELIVERY"]
CODE_RE = re.compile(r"^[A-Z0-9_-]{3,20}$")


class CouponBrief(BaseModel):
    """Checkout preview me: kaun sa coupon laga."""

    code: str
    title: str
    discount_type: str


class CouponOut(BaseModel):
    """Customer ko coupon ki list me (app isse card banati hai)."""

    id: uuid.UUID
    code: str
    title: str  # customer ki bhasha me
    discount_type: str  # FLAT / PERCENT / FREE_DELIVERY
    value: float  # FLAT: rupaye, PERCENT: percent, FREE_DELIVERY: 0
    max_discount: float | None
    min_order_amount: float
    first_order_only: bool
    seller_id: uuid.UUID | None  # bhara ho to coupon sirf us seller ke saaman par
    expires_at: datetime
    usable: bool  # is customer ke liye abhi chal sakta hai
    unusable_reason: str | None  # usable false ho to code (COUPON_USER_LIMIT...)
    unusable_message: str | None  # wahi, customer ki bhasha me


class CouponCreate(BaseModel):
    code: str
    title: str = Field(min_length=3, max_length=120)
    title_hi: str | None = Field(default=None, max_length=120)
    title_bho: str | None = Field(default=None, max_length=120)
    discount_type: DiscountType
    value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)  # FLAT: rupaye, PERCENT: 1-100
    max_discount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)  # sirf PERCENT
    min_order_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    funded_by: Literal["PLATFORM", "SELLER"] = "PLATFORM"
    seller_id: uuid.UUID | None = None  # SELLER-funded ho to zaroori
    first_order_only: bool = False
    is_public: bool = True
    per_user_limit: int = Field(default=1, ge=1, le=1000)
    total_limit: int | None = Field(default=None, ge=1)
    starts_at: AwareDatetime | None = None  # khali = abhi se
    expires_at: AwareDatetime

    @field_validator("code", mode="before")
    @classmethod
    def _code(cls, v):
        v = str(v or "").strip().upper()
        if not CODE_RE.match(v):
            raise ValueError("code 3-20 akshar ka ho: A-Z, 0-9, - ya _")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("title kam se kam 3 akshar ka ho")
        return v

    @field_validator("title_hi", "title_bho")
    @classmethod
    def _opt_title(cls, v):
        return (v.strip() or None) if v is not None else None

    @model_validator(mode="after")
    def _rules(self):
        if self.discount_type == "FLAT" and self.value <= 0:
            raise ValueError("FLAT coupon me value (rupaye) 0 se zyada honi chahiye")
        if self.discount_type == "PERCENT" and not (0 < self.value <= 100):
            raise ValueError("PERCENT coupon me value 0 se zyada aur 100 tak honi chahiye")
        if self.discount_type == "FREE_DELIVERY" and self.value != 0:
            raise ValueError("FREE_DELIVERY me value 0 rakho")
        if self.max_discount is not None and self.discount_type != "PERCENT":
            raise ValueError("max_discount sirf PERCENT coupon me hota hai")
        if self.discount_type == "FREE_DELIVERY" and self.funded_by != "PLATFORM":
            raise ValueError("FREE_DELIVERY ka kharcha sirf platform utha sakta hai")
        if self.funded_by == "SELLER" and self.seller_id is None:
            raise ValueError("SELLER-funded coupon me seller_id dena zaroori hai")
        if self.starts_at is not None and self.expires_at <= self.starts_at:
            raise ValueError("expires_at, starts_at ke baad ka hona chahiye")
        return self


class SellerCouponCreate(BaseModel):
    """Seller apna coupon banata hai. Discount seller ka apna kharcha hai (uske payout se kat'ta hai) aur sirf uske apne saaman par lagta hai.
    funded_by / seller_id yahan nahi dene padte: server khud lagata hai. Free delivery seller nahi de sakta (wo Padosi ka kharcha hai)."""

    code: str
    title: str = Field(min_length=3, max_length=120)
    title_hi: str | None = Field(default=None, max_length=120)
    title_bho: str | None = Field(default=None, max_length=120)
    discount_type: Literal["FLAT", "PERCENT"]
    value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)  # FLAT: rupaye, PERCENT: 1-100
    max_discount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)  # sirf PERCENT
    min_order_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    first_order_only: bool = False
    is_public: bool = True
    per_user_limit: int = Field(default=1, ge=1, le=1000)
    total_limit: int | None = Field(default=None, ge=1)
    starts_at: AwareDatetime | None = None
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def _same_rules(self):
        CouponCreate(**self.model_dump(), funded_by="SELLER", seller_id=uuid.UUID(int=0))  # admin wale coupon ke wahi niyam (code, value, tareekh...)
        return self


class CouponPatch(BaseModel):
    """Banne ke baad sirf ye badal sakte hain (discount ka niyam nahi). Jo bheja wahi badalta hai. Karan zaroori, audit log banta hai."""

    title: str | None = Field(default=None, min_length=3, max_length=120)
    title_hi: str | None = Field(default=None, max_length=120)
    title_bho: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    is_public: bool | None = None
    starts_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
    per_user_limit: int | None = Field(default=None, ge=1, le=1000)
    total_limit: int | None = Field(default=None, ge=1)  # null bhejo to limit hat jaati hai
    reason: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def _some(self):
        if not (self.model_fields_set - {"reason"}):
            raise ValueError("kam se kam ek cheez badlo")
        for f in ("title", "is_active", "is_public", "starts_at", "expires_at", "per_user_limit"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} khali nahi ho sakta")
        return self


class CouponAdminOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    title_hi: str | None
    title_bho: str | None
    discount_type: str
    value: float
    max_discount: float | None
    min_order_amount: float
    funded_by: str
    seller_id: uuid.UUID | None
    first_order_only: bool
    is_public: bool
    per_user_limit: int
    total_limit: int | None
    starts_at: datetime
    expires_at: datetime
    is_active: bool
    used_count: int  # abhi chal rahe (cancel na hue) orders me kitni baar laga
    total_discount_given: float  # unka kul discount
    created_at: datetime
