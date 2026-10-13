import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PickupItemOut(BaseModel):
    name: str
    quantity: int
    selling_unit: str


class PickupStoreOut(BaseModel):
    """Delivery boy ko is dukaan se ye saaman uthana hai (seller ne jo hataye wo shamil nahi)."""

    store_order_id: uuid.UUID
    store_name: str
    store_address: str
    latitude: float
    longitude: float
    status: str  # dukaan ka hissa: PLACED / SELLER_ACCEPTED / PREPARING / READY_FOR_PICKUP
    items: list[PickupItemOut]


class AvailableOrderOut(BaseModel):
    """Accept se pehle sirf itna dikhta hai. Customer ka naam / phone / address accept ke baad hi milta hai."""

    order_id: uuid.UUID
    order_number: str
    stores: list[PickupStoreOut]
    pickup_distance_km: float | None  # aapse sabse paas wali dukaan tak (lat/lng bhejne par)
    drop_distance_km: float  # dukaan se customer tak (sabse door wali dukaan se)
    delivery_fee: float
    payment_method: str
    amount_due: float  # COD me customer se kitna lena hai
    created_at: datetime


class MyDeliveryOut(BaseModel):
    delivery_id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    status: str  # delivery ka status (ASSIGNED ...)
    order_status: str
    assigned_at: datetime
    stores: list[PickupStoreOut]
    receiver_name: str
    receiver_phone: str
    address_line: str
    landmark: str | None
    latitude: float
    longitude: float
    delivery_fee: float
    payment_method: str
    amount_due: float


class ReleasedOut(BaseModel):
    order_id: uuid.UUID
    released: bool = True


class DeliverBody(BaseModel):
    otp: str = Field(pattern=r"^\d{4}$")  # customer ke paas wala 4 ank ka OTP


class DeliveredOut(BaseModel):
    order_id: uuid.UUID
    order_number: str
    status: str  # DELIVERED
    cod_collected: float  # COD me customer se liya hua cash (baaki me 0)
    delivered_at: datetime