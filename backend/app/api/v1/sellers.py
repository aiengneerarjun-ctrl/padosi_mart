from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.core.errors import api_error
from app.core.storage import public_url
from app.models import Seller, User
from app.schemas.seller import SellerApply, SellerOut
from app.services import seller as seller_service
from app.services.image_processing import MAX_UPLOAD_BYTES

router = APIRouter(prefix="/sellers", tags=["sellers"])


def _seller_out(seller: Seller) -> SellerOut:
    return SellerOut.model_validate({
        "id": seller.id, "seller_type": seller.seller_type, "store_category": seller.store_category,
        "store_image_medium_url": public_url(seller.store_image_key) if seller.store_image_key else None,
        "business_name": seller.business_name, "owner_name": seller.owner_name,
        "status": seller.status, "status_reason": seller.status_reason, "created_at": seller.created_at,
    })


@router.post("/apply", response_model=SellerOut, status_code=201)
async def apply(body: SellerApply, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return _seller_out(await seller_service.apply(db, user, body))


@router.get("/me", response_model=SellerOut)
async def my_seller(seller: Seller = Depends(get_current_seller)):
    return _seller_out(seller)


@router.post("/me/store-image", response_model=SellerOut)
async def upload_store_image(
    file: UploadFile = File(...), seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise api_error(413, "IMAGE_TOO_LARGE", "Photo bahut badi hai (max 5 MB).")
    return _seller_out(await seller_service.upload_store_image(db, seller, data))
