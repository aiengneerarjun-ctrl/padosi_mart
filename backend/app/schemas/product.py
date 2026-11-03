import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.storage import public_url

Money = Decimal  # paise tak (2 decimal) - float nahi, taaki hisaab me galti na ho


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    category_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=200)  # English
    name_hi: str | None = Field(default=None, max_length=200)
    name_bho: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    selling_unit: str = Field(min_length=1, max_length=50, examples=["1 kg", "500 ml", "6 pcs"])
    mrp: Money = Field(gt=0, max_digits=10, decimal_places=2)
    selling_price: Money = Field(gt=0, max_digits=10, decimal_places=2)
    initial_stock: int = Field(default=0, ge=0, le=1_000_000)
    low_stock_threshold: int = Field(default=5, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def price_not_above_mrp(self):
        if self.selling_price > self.mrp:
            raise ValueError("selling_price MRP se zyada nahi ho sakta")
        return self


class ProductUpdate(BaseModel):
    """Sirf bheje gaye fields badalte hain. SKU badla nahi jaa sakta."""

    barcode: str | None = Field(default=None, max_length=64)
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    name_hi: str | None = Field(default=None, max_length=200)
    name_bho: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    selling_unit: str | None = Field(default=None, min_length=1, max_length=50)
    mrp: Money | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    selling_price: Money | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    low_stock_threshold: int | None = Field(default=None, ge=0, le=1_000_000)


class ProductStatusBody(BaseModel):
    status: Literal["ACTIVE", "INACTIVE"]


class ProductCommissionBody(BaseModel):
    commission_mode: Literal["PERCENT", "FIXED"] = "PERCENT"
    commission_unit: Literal[
        "SALE_UNIT", "PIECE", "KG", "GRAM", "LITER", "ML", "BOTTLE",
        "METER", "BOX", "BUNDLE", "PACKET", "DOZEN", "PLATE", "SERVING", "JAR", "SACHET",
        "CAN", "CUP", "TRAY", "PAIR", "SET", "ROLL", "BAG", "POUCH", "DOSE", "CONTAINER", "TUB", "BASKET", "OTHER",
    ] = "SALE_UNIT"
    commission_value: Money = Field(ge=0, max_digits=10, decimal_places=4)
    commission_unit_quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=4)

    @model_validator(mode="after")
    def percentage_in_range(self):
        if self.commission_mode == "PERCENT" and self.commission_value > 100:
            raise ValueError("percentage commission 100 se zyada nahi ho sakta")
        return self


class StockAdjust(BaseModel):
    change: int = Field(ge=-1_000_000, le=1_000_000, description="+ stock aaya, - stock kam hua")
    reason: Literal["STOCK_IN", "ADJUSTMENT", "DAMAGED"] = "ADJUSTMENT"
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def not_zero(self):
        if self.change == 0:
            raise ValueError("change 0 nahi ho sakta")
        return self


class ProductImageOut(BaseModel):
    """Teen size ke URL. Listing card me thumb/medium, product detail me large."""

    id: uuid.UUID
    position: int  # 0 = primary image
    thumb_url: str
    medium_url: str
    large_url: str
    width: int
    height: int


class ImageOrderBody(BaseModel):
    image_ids: list[uuid.UUID] = Field(min_length=1, max_length=8)


class ProductOut(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    category_id: uuid.UUID
    brand_id: uuid.UUID | None
    sku: str
    barcode: str | None
    name: str
    name_hi: str | None
    name_bho: str | None
    description: str | None
    selling_unit: str
    commission_mode: str
    commission_unit: str
    commission_value: float
    commission_unit_quantity: float
    mrp: float
    selling_price: float
    discount_percent: int
    status: str
    status_reason: str | None
    stock: int
    low_stock: bool
    images: list[ProductImageOut]
    created_at: datetime


class AdminProductOut(ProductOut):
    store_name: str


class StockTransactionOut(BaseModel):
    id: uuid.UUID
    change: int
    quantity_after: int
    reason: str
    note: str | None
    created_at: datetime


def image_out(img) -> ProductImageOut:
    return ProductImageOut(
        id=img.id, position=img.position, width=img.width, height=img.height,
        thumb_url=public_url(f"{img.key_prefix}/thumb.webp"),
        medium_url=public_url(f"{img.key_prefix}/medium.webp"),
        large_url=public_url(f"{img.key_prefix}/large.webp"),
    )


def product_out(p, store_name: str | None = None) -> ProductOut | AdminProductOut:
    """Product + inventory se response banata hai (stock aur discount yahin nikalte hain)."""
    stock = p.inventory.quantity if p.inventory else 0
    threshold = p.inventory.low_stock_threshold if p.inventory else 0
    discount = int(round((p.mrp - p.selling_price) / p.mrp * 100)) if p.mrp else 0
    data = dict(
        id=p.id, store_id=p.store_id, category_id=p.category_id, brand_id=p.brand_id, sku=p.sku, barcode=p.barcode,
        name=p.name, name_hi=p.name_hi, name_bho=p.name_bho, description=p.description, selling_unit=p.selling_unit,
        commission_mode=getattr(p, "commission_mode", "PERCENT"),
        commission_unit=getattr(p, "commission_unit", "SALE_UNIT"),
        commission_value=float(getattr(p, "commission_value", 0)),
        commission_unit_quantity=float(getattr(p, "commission_unit_quantity", 1)),
        mrp=p.mrp, selling_price=p.selling_price, discount_percent=discount, status=p.status,
        status_reason=p.status_reason, stock=stock, low_stock=stock <= threshold,
        images=[image_out(i) for i in p.images], created_at=p.created_at,
    )
    if store_name is not None:
        return AdminProductOut(**data, store_name=store_name)
    return ProductOut(**data)
