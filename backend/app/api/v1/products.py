import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models import Seller, User
from app.models.catalog import ProductStatus
from app.schemas.product import (
    ProductCreate, ProductOut, ProductStatusBody, ProductUpdate, StockAdjust, StockTransactionOut, product_out,
)
from app.services import inventory as inventory_service
from app.services import product as product_service

# Seller ke product / stock routes. Har route me ownership check service me hota hai.
router = APIRouter(tags=["products"])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("/stores/{store_id}/products", response_model=ProductOut, status_code=201)
async def create_product(
    store_id: uuid.UUID, body: ProductCreate,
    seller: Seller = Depends(get_current_seller), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return product_out(await product_service.create_product(db, seller, store_id, user, body))


@router.get("/stores/{store_id}/products", response_model=list[ProductOut])
async def list_products(
    store_id: uuid.UUID, status: ProductStatus | None = None, limit: Limit = 20, offset: Offset = 0,
    seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db),
):
    rows = await product_service.list_store_products(db, seller, store_id, status.value if status else None, limit, offset)
    return [product_out(p) for p in rows]


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return product_out(await product_service.get_owned_product(db, seller, product_id))


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: uuid.UUID, body: ProductUpdate, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return product_out(await product_service.update_product(db, seller, product_id, body))


@router.post("/products/{product_id}/status", response_model=ProductOut)
async def set_status(product_id: uuid.UUID, body: ProductStatusBody, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    """Product ko chhupao (INACTIVE) ya wapas dikhao (ACTIVE)."""
    return product_out(await product_service.set_status(db, seller, product_id, body.status))


@router.post("/products/{product_id}/stock", response_model=ProductOut)
async def adjust_stock(
    product_id: uuid.UUID, body: StockAdjust,
    seller: Seller = Depends(get_current_seller), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return product_out(await product_service.adjust_product_stock(db, seller, user, product_id, body))


@router.get("/products/{product_id}/stock-history", response_model=list[StockTransactionOut])
async def stock_history(
    product_id: uuid.UUID, limit: Limit = 20, offset: Offset = 0,
    seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db),
):
    product = await product_service.get_owned_product(db, seller, product_id)
    rows = await inventory_service.stock_history(db, product.id, limit, offset)
    return [StockTransactionOut(id=r.id, change=r.change, quantity_after=r.quantity_after, reason=r.reason, note=r.note, created_at=r.created_at) for r in rows]