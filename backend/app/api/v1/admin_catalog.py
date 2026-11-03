import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import Store, User
from app.models.catalog import ProductStatus
from app.schemas.catalog import (
    AdminCategoryOut, BrandCreate, BrandOut, BrandUpdate, CategoryCreate, CategoryUpdate,
)
from app.schemas.product import AdminProductOut, ProductCommissionBody, product_out
from app.schemas.seller import ReasonBody
from app.services import catalog as catalog_service
from app.services import product as product_service

# Admin router: sab routes sirf Super Admin ke liye (router level par lagaya hai)
router = APIRouter(prefix="/admin", tags=["admin-catalog"], dependencies=[Depends(require_super_admin)])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


# ---- Categories ----
@router.get("/categories", response_model=list[AdminCategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_categories(db, only_active=False)


@router.post("/categories", response_model=AdminCategoryOut, status_code=201)
async def create_category(body: CategoryCreate, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await catalog_service.create_category(db, admin, request, body)


@router.patch("/categories/{category_id}", response_model=AdminCategoryOut)
async def update_category(category_id: uuid.UUID, body: CategoryUpdate, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await catalog_service.update_category(db, admin, request, category_id, body)


# ---- Brands ----
@router.get("/brands", response_model=list[BrandOut])
async def list_brands(db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_brands(db, only_active=False)


@router.post("/brands", response_model=BrandOut, status_code=201)
async def create_brand(body: BrandCreate, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await catalog_service.create_brand(db, admin, request, body)


@router.patch("/brands/{brand_id}", response_model=BrandOut)
async def update_brand(brand_id: uuid.UUID, body: BrandUpdate, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await catalog_service.update_brand(db, admin, request, brand_id, body)


# ---- Product approval ----
@router.get("/products", response_model=list[AdminProductOut])
async def list_products(status: ProductStatus | None = None, limit: Limit = 20, offset: Offset = 0, db: AsyncSession = Depends(get_db)):
    rows = await product_service.admin_list_products(db, status.value if status else None, limit, offset)
    return [product_out(p, store_name) for p, store_name in rows]


async def _admin_out(db: AsyncSession, product):
    store = await db.get(Store, product.store_id)
    return product_out(product, store.name)


@router.post("/products/{product_id}/approve", response_model=AdminProductOut)
async def approve_product(product_id: uuid.UUID, body: ProductCommissionBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await _admin_out(db, await product_service.approve(db, admin, request, product_id, body))


@router.patch("/products/{product_id}/commission", response_model=AdminProductOut)
async def set_product_commission(product_id: uuid.UUID, body: ProductCommissionBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await _admin_out(db, await product_service.set_commission(db, admin, request, product_id, body))


@router.post("/products/{product_id}/reject", response_model=AdminProductOut)
async def reject_product(product_id: uuid.UUID, body: ReasonBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await _admin_out(db, await product_service.reject(db, admin, request, product_id, body.reason))
