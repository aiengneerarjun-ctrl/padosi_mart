import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.seller import ShopStatus

StoreCategoryCode = Literal[
    "GROCERY", "RESTAURANT", "HARDWARE", "MEDICAL", "CLOTHING", "MOBILE_ELECTRONICS",
    "FOOTWEAR", "FRUITS_VEGETABLES", "DAIRY", "BAKERY", "STATIONERY", "BEAUTY_COSMETICS",
    "HOME_FURNITURE", "ELECTRICAL", "AUTO_PARTS", "PET_SUPPLIES", "BOOKS_GIFTS", "SPORTS",
    "AGRICULTURE", "OTHER",
]


class StoreCreate(BaseModel):
    store_category: StoreCategoryCode = "GROCERY"
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    cuisine: str | None = Field(default=None, max_length=100)
    address: str = Field(min_length=5, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    delivery_radius_km: float = Field(default=3, ge=0.5, le=25)
    min_order_amount: float = Field(default=0, ge=0)


class StoreUpdate(BaseModel):
    store_category: StoreCategoryCode | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    cuisine: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, min_length=5, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    delivery_radius_km: float | None = Field(default=None, ge=0.5, le=25)
    min_order_amount: float | None = Field(default=None, ge=0)


class StoreStatusBody(BaseModel):
    status: ShopStatus


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_type: str
    store_category: str
    image_medium_url: str | None = None
    name: str
    description: str | None
    cuisine: str | None
    address: str
    latitude: float
    longitude: float
    delivery_radius_km: float
    min_order_amount: float
    shop_status: str
    created_at: datetime
    
