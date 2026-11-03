import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller
from app.core.database import get_db
from app.models import Seller
from app.core.errors import api_error
from app.core.storage import public_url
from app.schemas.store import StoreCreate, StoreOut, StoreStatusBody, StoreUpdate
from app.services import store as store_service
from app.services.image_processing import MAX_UPLOAD_BYTES

router = APIRouter(prefix="/stores", tags=["stores"])


def _store_out(store) -> StoreOut:
    return StoreOut.model_validate({
        **{field: getattr(store, field) for field in StoreOut.model_fields if field != "image_medium_url"},
        "image_medium_url": public_url(store.image_key) if store.image_key else None,
    })


@router.post("", response_model=StoreOut, status_code=201)
async def create_store(body: StoreCreate, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return _store_out(await store_service.create_store(db, seller, body))


@router.get("/mine", response_model=list[StoreOut])
async def my_stores(seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return [_store_out(store) for store in await store_service.list_my_stores(db, seller)]


@router.post("/{store_id}/image", response_model=StoreOut)
async def upload_store_image(
    store_id: uuid.UUID, file: UploadFile = File(...), seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise api_error(413, "IMAGE_TOO_LARGE", "Photo bahut badi hai (max 5 MB).")
    return _store_out(await store_service.upload_store_image(db, seller, store_id, data))


@router.patch("/{store_id}", response_model=StoreOut)
async def update_store(
    store_id: uuid.UUID, body: StoreUpdate, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)
):
    return _store_out(await store_service.update_store(db, seller, store_id, body))


@router.post("/{store_id}/status", response_model=StoreOut)
async def set_status(
    store_id: uuid.UUID, body: StoreStatusBody, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)
):
    """Seller manually dukaan OPEN/CLOSED karta hai."""
    return _store_out(await store_service.set_shop_status(db, seller, store_id, body.status))
