import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

RemovalReasonCode = Literal["OUT_OF_STOCK", "QUALITY_ISSUE", "SHOP_CLOSING", "OTHER"]


class SellerOrderItem(BaseModel):
    id: uuid.UUID  # order item ki id: "saaman nahi hai" isi se bhejte hain
    product_id: uuid.UUID
    name: str
    selling_unit: str
    quantity: int
    unit_price: float
    line_total: float
    removed: bool = False  # is item ko seller hata chuka hai
    removed_reason_code: str | None = None
    removed_reason: str | None = None
    removed_kept_quantity: int | None = None  # aadha saaman: itne piece dukaan ne de diye (nayi line me)


class SellerOrderOut(BaseModel):
    """Seller ko apni dukaan ka hissa dikhta hai. Customer ka phone/address seller ko nahi dikhta."""

    id: uuid.UUID  # store_order id: accept/reject isi par
    order_id: uuid.UUID
    order_number: str  # jaise PD1001
    store_id: uuid.UUID
    store_name: str
    status: str
    payment_method: str  # COD / ONLINE
    items_subtotal: float  # is dukaan ka total, hataye gaye items ke baad (commission kaatne se pehle)
    seller_discount: float = 0.0  # seller-funded coupon me tumhara hissa: ye tumhare payout se kat'ta hai
    items: list[SellerOrderItem]
    created_at: datetime
    updated_at: datetime


class UnavailableItem(BaseModel):
    item_id: uuid.UUID
    reason: RemovalReasonCode = "OUT_OF_STOCK"
    note: str | None = Field(default=None, max_length=200)  # customer ko dikhta hai
    # Aadha saaman: dukaan ke paas itne piece hain (maange se kam). 0 = ek bhi nahi (poora item hat jaata hai).
    available_quantity: int = Field(default=0, ge=0, le=100000)


class UnavailableBody(BaseModel):
    items: list[UnavailableItem] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def no_duplicates(self):
        ids = [i.item_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("ek item do baar nahi bhej sakte")
        return self


class RejectBody(BaseModel):
    """Poori dukaan ka hissa lene se mana (saare items hat jaate hain). Karan likhna zaroori; customer ko dikhta hai."""

    reason: str = Field(min_length=3, max_length=200)
    reason_code: RemovalReasonCode = "OTHER"