import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller
from app.core.database import get_db
from app.models import Seller
from app.schemas.store import StoreCreate, StoreOut, StoreStatusBody, StoreUpdate
from app.services import store as store_service

router = APIRouter(prefix="/stores", tags=["stores"])


@router.post("", response_model=StoreOut, status_code=201)
async def create_store(body: StoreCreate, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return await store_service.create_store(db, seller, body)


@router.get("/mine", response_model=list[StoreOut])
async def my_stores(seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return await store_service.list_my_stores(db, seller)


@router.patch("/{store_id}", response_model=StoreOut)
async def update_store(
    store_id: uuid.UUID, body: StoreUpdate, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)
):
    return await store_service.update_store(db, seller, store_id, body)


@router.post("/{store_id}/status", response_model=StoreOut)
async def set_status(
    store_id: uuid.UUID, body: StoreStatusBody, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)
):
    """Seller manually dukaan OPEN/CLOSED karta hai."""
    return await store_service.set_shop_status(db, seller, store_id, body.status)