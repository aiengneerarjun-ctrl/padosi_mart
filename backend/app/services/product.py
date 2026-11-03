import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Seller, Store, User
from app.models.catalog import Brand, Category, Inventory, Product, ProductStatus, StockReason
from app.models.seller import SellerStatus
from app.schemas.product import ProductCommissionBody, ProductCreate, ProductUpdate, StockAdjust
from app.services import inventory as inventory_service
from app.services.audit import write_audit
from app.services.store import get_owned_store

# In fields ke badalne par admin ko dobara approve karna padta hai (warna approve ke baad naam/photo
# badal kar customer ko dhokha diya jaa sakta hai). Price aur stock badalne par dobara approval nahi.
IDENTITY_FIELDS = {"name", "name_hi", "name_bho", "description", "category_id", "brand_id", "selling_unit"}
NULLABLE_FIELDS = {"name_hi", "name_bho", "description", "brand_id", "barcode"}


def _require_active(seller: Seller) -> None:
    if seller.status != SellerStatus.ACTIVE:
        raise api_error(403, "SELLER_NOT_ACTIVE", "Aapka seller account abhi active nahi hai.")


async def load_product(db: AsyncSession, product_id: uuid.UUID) -> Product | None:
    """Fresh product + inventory (purana cached object nahi)."""
    q = select(Product).where(Product.id == product_id).execution_options(populate_existing=True)
    return await db.scalar(q)


async def get_owned_product(db: AsyncSession, seller: Seller, product_id: uuid.UUID) -> Product:
    product = await load_product(db, product_id)
    store = await db.get(Store, product.store_id) if product else None
    # Doosre seller ke product ka bhi 404 (pata hi na chale ki wo hai)
    if product is None or store.seller_id != seller.id:
        raise api_error(404, "PRODUCT_NOT_FOUND", "Product nahi mila.")
    return product


async def _check_category_brand(db: AsyncSession, category_id: uuid.UUID | None, brand_id: uuid.UUID | None) -> None:
    if category_id is not None:
        category = await db.get(Category, category_id)
        if category is None or not category.is_active:
            raise api_error(404, "CATEGORY_NOT_FOUND", "Category nahi mili.")
    if brand_id is not None:
        brand = await db.get(Brand, brand_id)
        if brand is None or not brand.is_active:
            raise api_error(404, "BRAND_NOT_FOUND", "Brand nahi mila.")


def _status_for_stock(quantity: int) -> ProductStatus:
    return ProductStatus.ACTIVE if quantity > 0 else ProductStatus.OUT_OF_STOCK


async def create_product(db: AsyncSession, seller: Seller, store_id: uuid.UUID, user: User, body: ProductCreate) -> Product:
    _require_active(seller)
    store = await get_owned_store(db, seller, store_id)
    await _check_category_brand(db, body.category_id, body.brand_id)

    data = body.model_dump(exclude={"initial_stock", "low_stock_threshold"})
    product = Product(store_id=store.id, status=ProductStatus.PENDING_APPROVAL, **data)
    product.inventory = Inventory(quantity=0, low_stock_threshold=body.low_stock_threshold)
    db.add(product)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "SKU_EXISTS", "Ye SKU aapki dukaan me pehle se maujood hai.")
    if body.initial_stock > 0:
        await inventory_service.adjust_stock(db, product.id, body.initial_stock, StockReason.INITIAL, user)
    await db.commit()
    return await load_product(db, product.id)


async def list_store_products(
    db: AsyncSession, seller: Seller, store_id: uuid.UUID, status: str | None, limit: int, offset: int
) -> list[Product]:
    store = await get_owned_store(db, seller, store_id)
    q = select(Product).where(Product.store_id == store.id).order_by(Product.created_at.desc())
    if status:
        q = q.where(Product.status == status)
    return list(await db.scalars(q.limit(limit).offset(offset)))


async def update_product(db: AsyncSession, seller: Seller, product_id: uuid.UUID, body: ProductUpdate) -> Product:
    _require_active(seller)
    product = await get_owned_product(db, seller, product_id)
    changes = {
        k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None or k in NULLABLE_FIELDS
    }
    await _check_category_brand(db, changes.get("category_id"), changes.get("brand_id"))

    identity_changed = False
    for field, value in changes.items():
        if field == "low_stock_threshold":
            product.inventory.low_stock_threshold = value
            continue
        if field in IDENTITY_FIELDS and getattr(product, field) != value:
            identity_changed = True
        setattr(product, field, value)

    if product.selling_price > product.mrp:
        await db.rollback()
        raise api_error(422, "INVALID_PRICE", "Selling price MRP se zyada nahi ho sakta.")

    # REJECTED product me koi bhi edit = dobara review ke liye bhejna. Baaki me sirf identity badalne par.
    if product.status == ProductStatus.REJECTED or (identity_changed and product.status != ProductStatus.PENDING_APPROVAL):
        product.status = ProductStatus.PENDING_APPROVAL
        product.status_reason = None
    await db.commit()
    return await load_product(db, product.id)


async def set_status(db: AsyncSession, seller: Seller, product_id: uuid.UUID, target: str) -> Product:
    """Seller product ko chhupa (INACTIVE) ya wapas dikha (ACTIVE) sakta hai. Dukaan band karne se alag cheez."""
    _require_active(seller)
    product = await get_owned_product(db, seller, product_id)
    if target == "INACTIVE":
        allowed = {ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK}
        new_status = ProductStatus.INACTIVE
    else:
        allowed = {ProductStatus.INACTIVE}
        new_status = _status_for_stock(product.inventory.quantity)
    if product.status not in allowed:
        raise api_error(409, "INVALID_STATE", "Is stage par ye kaam nahi ho sakta.")
    product.status = new_status
    await db.commit()
    return await load_product(db, product.id)


async def adjust_product_stock(db: AsyncSession, seller: Seller, user: User, product_id: uuid.UUID, body: StockAdjust) -> Product:
    _require_active(seller)
    product = await get_owned_product(db, seller, product_id)
    await inventory_service.adjust_stock(db, product.id, body.change, StockReason(body.reason), user, body.note)
    await db.commit()
    return await load_product(db, product.id)


# ---------------- Admin ----------------


async def admin_list_products(db: AsyncSession, status: str | None, limit: int, offset: int):
    q = select(Product, Store.name).join(Store, Store.id == Product.store_id).order_by(Product.created_at.desc())
    if status:
        q = q.where(Product.status == status)
    return (await db.execute(q.limit(limit).offset(offset))).all()


async def _admin_transition(
    db: AsyncSession, admin: User, request: Request, product_id: uuid.UUID, *, allowed_from: set[str], to: str, action: str, reason: str | None
) -> Product:
    product = await load_product(db, product_id)
    if product is None:
        raise api_error(404, "PRODUCT_NOT_FOUND", "Product nahi mila.")
    if product.status not in allowed_from:
        raise api_error(409, "INVALID_STATE", "Is stage par ye kaam nahi ho sakta.")
    old = {"status": str(product.status), "status_reason": product.status_reason}
    product.status = to
    product.status_reason = reason
    write_audit(db, actor=admin, action=action, target_type="product", target_id=product.id,
                old=old, new={"status": str(to), "status_reason": reason}, reason=reason, request=request)
    await db.commit()
    return await load_product(db, product.id)


async def approve(db: AsyncSession, admin: User, request: Request, product_id: uuid.UUID, commission: ProductCommissionBody) -> Product:
    product = await load_product(db, product_id)
    if product is not None and not product.images:
        raise api_error(409, "PRODUCT_NEEDS_IMAGE", "Product me kam se kam ek photo zaroori hai.")
    if product is None:
        raise api_error(404, "PRODUCT_NOT_FOUND", "Product nahi mila.")
    qty = product.inventory.quantity if product and product.inventory else 0
    old = {
        "mode": product.commission_mode, "unit": product.commission_unit,
        "value": str(product.commission_value), "unit_quantity": str(product.commission_unit_quantity),
    }
    product.commission_mode = commission.commission_mode
    product.commission_unit = commission.commission_unit
    product.commission_value = commission.commission_value
    product.commission_unit_quantity = commission.commission_unit_quantity
    write_audit(
        db, actor=admin, action="product.set_commission", target_type="product", target_id=product.id,
        old=old,
        new={
            "mode": commission.commission_mode, "unit": commission.commission_unit,
            "value": str(commission.commission_value), "unit_quantity": str(commission.commission_unit_quantity),
        },
        reason="Product approval commission rule", request=request,
    )
    return await _admin_transition(
        db, admin, request, product_id,
        allowed_from={ProductStatus.PENDING_APPROVAL}, to=_status_for_stock(qty), action="product.approve", reason=None,
    )


async def set_commission(db: AsyncSession, admin: User, request: Request, product_id: uuid.UUID, commission: ProductCommissionBody) -> Product:
    product = await load_product(db, product_id)
    if product is None:
        raise api_error(404, "PRODUCT_NOT_FOUND", "Product nahi mila.")
    old = {
        "mode": product.commission_mode, "unit": product.commission_unit,
        "value": str(product.commission_value), "unit_quantity": str(product.commission_unit_quantity),
    }
    product.commission_mode = commission.commission_mode
    product.commission_unit = commission.commission_unit
    product.commission_value = commission.commission_value
    product.commission_unit_quantity = commission.commission_unit_quantity
    write_audit(
        db, actor=admin, action="product.set_commission", target_type="product", target_id=product.id,
        old=old,
        new={
            "mode": commission.commission_mode, "unit": commission.commission_unit,
            "value": str(commission.commission_value), "unit_quantity": str(commission.commission_unit_quantity),
        },
        reason="Admin updated product commission", request=request,
    )
    await db.commit()
    return await load_product(db, product.id)


async def reject(db: AsyncSession, admin: User, request: Request, product_id: uuid.UUID, reason: str) -> Product:
    # PENDING ko reject, ya live product ko neeche utaarna (takedown) - dono yahin
    return await _admin_transition(
        db, admin, request, product_id,
        allowed_from={ProductStatus.PENDING_APPROVAL, ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK, ProductStatus.INACTIVE},
        to=ProductStatus.REJECTED, action="product.reject", reason=reason,
    )
