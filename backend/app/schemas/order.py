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


class StoreOrderOut(BaseModel):
    """Ek dukaan ka hissa: delivery boy yahan se uthayega, seller ka paisa isi subtotal se banega."""

    id: uuid.UUID
    store_id: uuid.UUID
    store_name: str
    store_address: str
    status: str
    items_subtotal: float
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
    items_subtotal: float
    delivery_fee: float
    total: float
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
    store_names: list[str]
    item_count: int
    created_at: datetime