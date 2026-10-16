from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.coupon import CouponOut
from app.services import coupon as service

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.get("", response_model=list[CouponOut])
async def my_coupons(
    request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Abhi chal rahe public coupons (usable=false ho to unusable_reason / unusable_message dikhao).
    Coupon lagane ke liye: GET /checkout/preview?coupon_code=XXX, phir order me wahi coupon_code bhejo."""
    return await service.list_for_customer(db, user, limit, offset, request.state.lang)
