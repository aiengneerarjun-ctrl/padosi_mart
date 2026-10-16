import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ReviewCreate(BaseModel):
    order_id: uuid.UUID
    target: Literal["STORE", "PARTNER"]  # dukaan ka ya delivery partner ka
    store_id: uuid.UUID | None = None  # STORE ke liye zaroori, PARTNER ke liye nahi
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("comment")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None  # khali comment = comment nahi

    @model_validator(mode="after")
    def _target(self):
        if self.target == "STORE" and self.store_id is None:
            raise ValueError("dukaan ke review me store_id do")
        if self.target == "PARTNER" and self.store_id is not None:
            raise ValueError("delivery partner ke review me store_id nahi dena")
        return self


class RatingSummaryOut(BaseModel):
    average: float | None  # review nahi hai to None
    count: int
    stars: dict[int, int]  # {1: kitne, ..., 5: kitne}


class ReviewTargetOut(BaseModel):
    target: str  # STORE / PARTNER
    store_id: uuid.UUID | None
    name: str  # dukaan ka naam, ya delivery partner ka pehla naam
    reviewed: bool
    review_id: uuid.UUID | None


class ReviewableOut(BaseModel):
    order_id: uuid.UUID
    can_review: bool  # abhi review de sakta hai
    reason: str | None  # can_review false ho to code (REVIEW_ORDER_NOT_DELIVERED / REVIEW_WINDOW_OVER)
    message: str | None  # wahi, customer ki bhasha me
    review_until: datetime | None
    targets: list[ReviewTargetOut]


class ReviewOut(BaseModel):
    """Customer ko apna review."""

    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    target: str
    store_id: uuid.UUID | None
    name: str
    rating: int
    comment: str | None
    is_hidden: bool
    created_at: datetime


class PublicReviewOut(BaseModel):
    rating: int
    comment: str | None
    reviewer_name: str  # sirf pehla naam (ya "Customer")
    created_at: datetime


class StoreReviewsOut(BaseModel):
    summary: RatingSummaryOut
    reviews: list[PublicReviewOut]


class SellerReviewOut(PublicReviewOut):
    id: uuid.UUID
    store_id: uuid.UUID
    store_name: str
    order_number: str


class SellerReviewsOut(BaseModel):
    summary: RatingSummaryOut  # sab (ya chuni hui) dukaan ka
    reviews: list[SellerReviewOut]


class PartnerReviewOut(BaseModel):
    """Delivery partner ko: customer ka naam nahi dikhta."""

    rating: int
    comment: str | None
    order_number: str
    created_at: datetime


class PartnerReviewsOut(BaseModel):
    summary: RatingSummaryOut
    reviews: list[PartnerReviewOut]


class AdminReviewOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    target: str
    store_id: uuid.UUID | None
    store_name: str | None
    partner_id: uuid.UUID | None
    partner_name: str | None
    user_id: uuid.UUID
    reviewer_name: str | None
    rating: int
    comment: str | None
    status: str
    hidden_reason: str | None
    hidden_at: datetime | None
    created_at: datetime


class HideBody(BaseModel):
    reason: str = Field(min_length=3, max_length=300)  # kyun chhupaya (audit me jata hai)
