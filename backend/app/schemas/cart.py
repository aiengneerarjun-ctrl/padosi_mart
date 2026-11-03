import uuid

from pydantic import BaseModel, Field

from app.models.cart import MAX_ITEM_QTY


class CartItemSet(BaseModel):
    """Quantity set karo (add ya badalna, dono yahi). lat/lng customer ki delivery location."""

    quantity: int = Field(ge=1, le=MAX_ITEM_QTY)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class CartItemOut(BaseModel):
    product_id: uuid.UUID
    name: str  # customer ki bhasha me
    selling_unit: str
    mrp: float
    selling_price: float
    quantity: int
    line_total: float  # selling_price x quantity
    image_thumb_url: str | None
    available: bool  # false ho to ye item checkout me nahi ginega
    unavailable_reason: str | None  # PRODUCT_INACTIVE / STORE_CLOSED / SELLER_INACTIVE / NOT_DELIVERABLE / OUT_OF_STOCK / LOW_STOCK
    stock_left: int


class CartStoreGroup(BaseModel):
    """Ek dukaan ka hissa. Delivery boy ke liye: is dukaan se ye items uthane hain."""

    store_id: uuid.UUID
    store_name: str
    store_type: str
    store_category: str
    image_medium_url: str | None
    store_address: str
    distance_km: float  # customer se
    items: list[CartItemOut]
    subtotal: float  # sirf available items ka
    

class CartOut(BaseModel):
    stores: list[CartStoreGroup]
    item_count: int  # total quantity
    subtotal: float  # saari dukaanon ka (sirf available items)
    max_store_gap_km: float
    has_problems: bool  # koi item unavailable / stock kam
