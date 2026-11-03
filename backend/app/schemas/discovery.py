import uuid

from pydantic import BaseModel

from app.schemas.product import ProductImageOut


class StoreBrief(BaseModel):
    """Product ke saath hamesha dikhta hai, taaki customer ko pata rahe ye kis dukaan/restaurant ka hai."""

    id: uuid.UUID
    name: str
    store_type: str  # KIRANA ya RESTAURANT
    store_category: str
    image_medium_url: str | None
    cuisine: str | None


class StoreCard(StoreBrief):
    description: str | None
    distance_km: float
    eta_minutes: int  # andaaza (estimate)
    min_order_amount: float


class StoreDetail(StoreCard):
    address: str
    shop_status: str  # OPEN / CLOSED
    deliverable: bool  # customer is dukaan ke delivery radius ke andar hai
    can_order: bool  # OPEN + seller ACTIVE + deliverable


class ProductCard(BaseModel):
    id: uuid.UUID
    name: str  # customer ki bhasha me
    selling_unit: str
    mrp: float
    selling_price: float
    discount_percent: int
    image_thumb_url: str | None
    image_medium_url: str | None
    brand_name: str | None
    only_left: int | None  # stock bahut kam ho to "sirf X bache hain"
    distance_km: float
    eta_minutes: int
    store: StoreBrief


class ProductDetail(ProductCard):
    description: str | None
    category_id: uuid.UUID
    images: list[ProductImageOut]


class StoreCategory(BaseModel):
    id: uuid.UUID
    name: str  # customer ki bhasha me
    product_count: int


class Suggestions(BaseModel):
    products: list[str]
    stores: list[StoreBrief]
