import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models import Seller, User
from app.schemas.coupon import CouponAdminOut, CouponPatch, SellerCouponCreate
from app.services import coupon as service

# Seller apne coupons: discount seller ke payout se kat'ta hai aur sirf uske apne saaman par lagta hai.
router = APIRouter(prefix="/seller/coupons", tags=["seller-coupons"])


@router.post("", response_model=CouponAdminOut, status_code=201)
async def create_coupon(
    body: SellerCouponCreate, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Apna naya coupon. Discount ka niyam (type, value) banne ke baad badalta nahi: badalna ho to naya coupon banao."""
    return await service.seller_create(db, user, seller, request, body)


@router.get("", response_model=list[CouponAdminOut])
async def my_coupons(
    active: bool | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db),
):
    return await service.seller_list(db, seller, active, limit, offset)


@router.get("/{coupon_id}", response_model=CouponAdminOut)
async def get_coupon(coupon_id: uuid.UUID, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return await service.seller_get(db, seller, coupon_id)


@router.patch("/{coupon_id}", response_model=CouponAdminOut)
async def update_coupon(
    coupon_id: uuid.UUID, body: CouponPatch, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Naam, band/chalu, tareekh, limit badalo. Coupon hatana nahi, band karna (is_active=false)."""
    return await service.seller_patch(db, user, seller, request, coupon_id, body)
