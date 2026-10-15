import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    address_id: uuid.UUID | None = None  # na do to default address
    payment_method: Literal["COD", "ONLINE"] = "COD"
    # Customer ne preview me jo total dekha tha. Beech me price badli to order nahi banta (PRICE_CHANGED).
    expected_total: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    note: str | None = Field(default=None, max_length=300)


class OrderCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class OrderItemOut(BaseModel):
    product_id: uuid.UUID
    name: str  # customer ki bhasha me
    selling_unit: str
    mrp: float
    unit_price: float
    quantity: int
    line_total: float
    # Seller ne ye item hata diya ho to: removed=true, aur karan customer ki bhasha me
    removed: bool = False
    removed_reason_code: str | None = None
    removed_reason: str | None = None
    removed_note: str | None = None
    removed_kept_quantity: int | None = None  # aadha saaman: itne piece mil gaye (nayi line me)


class RemovedItemOut(BaseModel):
    """Seller ne jo item hataya: customer ke liye alag list (banner / "ye saaman nahi mila" screen)."""

    product_id: uuid.UUID
    name: str  # customer ki bhasha me
    selling_unit: str
    quantity: int
    line_total: float  # itne rupaye ghate
    store_name: str
    reason_code: str
    reason: str  # customer ki bhasha me
    note: str | None
    kept_quantity: int | None = None  # aadha saaman: itne piece mil gaye; quantity / line_total sirf hata hua hissa


class StoreOrderOut(BaseModel):
    """Ek dukaan ka hissa: delivery boy yahan se uthayega, seller ka paisa isi subtotal se banega."""

    id: uuid.UUID
    store_id: uuid.UUID
    store_name: str
    store_address: str
    status: str
    items_subtotal: float  # hataye gaye items ke baad ka
    items: list[OrderItemOut]


class AddressSnapshotOut(BaseModel):
    receiver_name: str
    receiver_phone: str
    address_line: str
    landmark: str | None
    latitude: float
    longitude: float


class StatusHistoryOut(BaseModel):
    store_order_id: uuid.UUID | None
    from_status: str | None
    to_status: str
    actor_role: str
    note: str | None
    created_at: datetime


class OrderOut(BaseModel):
    id: uuid.UUID
    order_number: str  # jaise PD1001
    status: str
    payment_method: str
    payment_status: str
    address: AddressSnapshotOut
    items_subtotal: float  # abhi ka (hataye gaye items ke baad)
    delivery_fee: float
    total: float  # abhi ka naya total
    # Hisaab: original_total - removed_total = total (delivery charge waisa hi)
    original_items_subtotal: float
    original_total: float
    removed_total: float
    delivery_fee_added: float  # items hatne se total 799 se neeche gaya to jo delivery charge naya laga (warna 0)
    can_cancel: bool  # customer abhi order cancel kar sakta hai
    seller_can_accept_after: datetime | None  # item hatne ke baad seller isse pehle accept nahi kar sakta (cancel ka mauka)
    amount_due: float  # COD me delivery par kitna dena hai (cancel/paid order me 0)
    delivery_otp: str | None = None  # sirf OUT_FOR_DELIVERY me: delivery partner ko batane ka4 ank ka OTP
    refunded_total: float = 0.0  # ONLINE order me ab tak wapas kiya (ya wapas ho raha) paisa
    payment_expires_at: datetime | None = None  # ONLINE order me isse pehle payment karna hai (warna order cancel)
    removed_items: list[RemovedItemOut]
    notice: str | None  # customer ki bhasha me ek line ka sandesh (kuch hata ho tab)
    note: str | None
    created_at: datetime
    stores: list[StoreOrderOut]
    history: list[StatusHistoryOut]


class OrderSummary(BaseModel):
    id: uuid.UUID
    order_number: str
    status: str
    payment_method: str
    payment_status: str
    total: float
    has_removed_items: bool
    store_names: list[str]
    item_count: int  # hataye gaye items ke bina
    created_at: datetime