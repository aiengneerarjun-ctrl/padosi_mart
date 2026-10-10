import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import User
from app.models.catalog import Brand, Category
from app.schemas.catalog import BrandCreate, BrandUpdate, CategoryCreate, CategoryUpdate
from app.services.audit import write_audit


async def list_categories(db: AsyncSession, *, only_active: bool, parent_id: uuid.UUID | None = None) -> list[Category]:
    q = select(Category).order_by(Category.sort_order, Category.name)
    if only_active:
        q = q.where(Category.is_active.is_(True))
    if parent_id is not None:
        q = q.where(Category.parent_id == parent_id)
    return list(await db.scalars(q))


async def create_category(db: AsyncSession, admin: User, request: Request, body: CategoryCreate) -> Category:
    if body.parent_id is not None:
        parent = await db.get(Category, body.parent_id)
        if parent is None:
            raise api_error(404, "CATEGORY_NOT_FOUND", "Category nahi mili.")
        if parent.parent_id is not None:
            raise api_error(422, "CATEGORY_TOO_DEEP", "Sub-category ke andar sub-category nahi ban sakti.")
    category = Category(**body.model_dump())
    db.add(category)
    await db.flush()
    write_audit(db, actor=admin, action="category.create", target_type="category", target_id=category.id,
                new=body.model_dump(mode="json"), request=request)
    await db.commit()
    return category


async def update_category(db: AsyncSession, admin: User, request: Request, category_id: uuid.UUID, body: CategoryUpdate) -> Category:
    category = await db.get(Category, category_id)
    if category is None:
        raise api_error(404, "CATEGORY_NOT_FOUND", "Category nahi mili.")
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in ("name_hi", "name_bho") or v is not None}
    old = {k: getattr(category, k) for k in changes}
    for field, value in changes.items():
        setattr(category, field, value)
    write_audit(db, actor=admin, action="category.update", target_type="category", target_id=category.id,
                old=old, new=changes, request=request)
    await db.commit()
    return category


async def list_brands(db: AsyncSession, *, only_active: bool) -> list[Brand]:
    q = select(Brand).order_by(Brand.name)
    if only_active:
        q = q.where(Brand.is_active.is_(True))
    return list(await db.scalars(q))


async def create_brand(db: AsyncSession, admin: User, request: Request, body: BrandCreate) -> Brand:
    brand = Brand(name=body.name.strip())
    db.add(brand)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "BRAND_EXISTS", "Ye brand pehle se maujood hai.")
    write_audit(db, actor=admin, action="brand.create", target_type="brand", target_id=brand.id,
                new={"name": brand.name}, request=request)
    await db.commit()
    return brand


async def update_brand(db: AsyncSession, admin: User, request: Request, brand_id: uuid.UUID, body: BrandUpdate) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise api_error(404, "BRAND_NOT_FOUND", "Brand nahi mila.")
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    old = {k: getattr(brand, k) for k in changes}
    for field, value in changes.items():
        setattr(brand, field, value.strip() if isinstance(value, str) else value)
    write_audit(db, actor=admin, action="brand.update", target_type="brand", target_id=brand.id,
                old=old, new=changes, request=request)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "BRAND_EXISTS", "Ye brand pehle se maujood hai.")
    return brand