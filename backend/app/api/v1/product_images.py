import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller
from app.core.database import get_db
from app.core.errors import api_error
from app.models import Seller
from app.schemas.product import ImageOrderBody, ProductOut, product_out
from app.services import product_image as image_service
from app.services.image_processing import MAX_UPLOAD_BYTES

# Seller ki product photos. Har route ProductOut lautata hai (images + naya status ek saath).
router = APIRouter(tags=["product-images"])


@router.post("/products/{product_id}/images", response_model=ProductOut, status_code=201)
async def upload_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """JPG/PNG/WebP, max 5 MB, kam se kam 400x400. Pehli photo primary hoti hai."""
    data = await file.read(MAX_UPLOAD_BYTES + 1)  # itna hi padhte hain, aage ki file memory me nahi lete
    if len(data) > MAX_UPLOAD_BYTES:
        raise api_error(413, "IMAGE_TOO_LARGE", "Photo bahut badi hai (max 5 MB).")
    return product_out(await image_service.add_image(db, seller, product_id, data))


@router.put("/products/{product_id}/images/order", response_model=ProductOut)
async def reorder_images(
    product_id: uuid.UUID, body: ImageOrderBody, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)
):
    """Photo ki nayi line bhejo (image ids). Pehli id primary banegi."""
    return product_out(await image_service.reorder_images(db, seller, product_id, body.image_ids))


@router.delete("/products/{product_id}/images/{image_id}", response_model=ProductOut)
async def delete_image(
    product_id: uuid.UUID, image_id: uuid.UUID, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)
):
    return product_out(await image_service.delete_image(db, seller, product_id, image_id))