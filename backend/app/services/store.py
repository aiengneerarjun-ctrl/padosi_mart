import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Seller, Store
from app.models.seller import SellerStatus, ShopStatus
from app.schemas.store import StoreCreate, StoreUpdate


def _require_active(seller: Seller) -> None:
    if seller.status != SellerStatus.ACTIVE:
        raise api_error(403, "SELLER_NOT_ACTIVE", "Aapka seller account abhi active nahi hai.")


async def create_store(db: AsyncSession, seller: Seller, body: StoreCreate) -> Store:
    _require_active(seller)
    store = Store(
        seller_id=seller.id,
        store_type=seller.seller_type,
        shop_status=ShopStatus.CLOSED,  # nayi dukaan band se shuru, seller khud OPEN karta hai
        **body.model_dump(),
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return store


async def get_owned_store(db: AsyncSession, seller: Seller, store_id: uuid.UUID) -> Store:
    store = await db.get(Store, store_id)
    # Doosre seller ki dukaan ka 404 dete hain (403 nahi), taaki pata hi na chale ki wo maujood hai
    if store is None or store.seller_id != seller.id:
        raise api_error(404, "STORE_NOT_FOUND", "Dukaan nahi mili.")
    return store


async def list_my_stores(db: AsyncSession, seller: Seller) -> list[Store]:
    result = await db.scalars(select(Store).where(Store.seller_id == seller.id).order_by(Store.created_at))
    return list(result)


async def update_store(db: AsyncSession, seller: Seller, store_id: uuid.UUID, body: StoreUpdate) -> Store:
    _require_active(seller)
    store = await get_owned_store(db, seller, store_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(store, field, value)
    await db.commit()
    await db.refresh(store)
    return store


async def set_shop_status(db: AsyncSession, seller: Seller, store_id: uuid.UUID, status: ShopStatus) -> Store:
    store = await get_owned_store(db, seller, store_id)
    # CLOSE hamesha allowed; OPEN sirf ACTIVE seller kar sakta hai
    if status == ShopStatus.OPEN:
        _require_active(seller)
    store.shop_status = status
    await db.commit()
    await db.refresh(store)
    return store