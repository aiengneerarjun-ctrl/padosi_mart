from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models import Seller, User
from app.schemas.seller import SellerApply, SellerOut
from app.services import seller as seller_service

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.post("/apply", response_model=SellerOut, status_code=201)
async def apply(body: SellerApply, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await seller_service.apply(db, user, body)


@router.get("/me", response_model=SellerOut)
async def my_seller(seller: Seller = Depends(get_current_seller)):
    return seller