import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.coupon import CouponAdminOut, CouponCreate, CouponPatch
from app.services import coupon as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/coupons", tags=["admin-coupons"], dependencies=[Depends(require_super_admin)])


@router.post("", response_model=CouponAdminOut, status_code=201)
async def create_coupon(body: CouponCreate, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Naya coupon. Discount ka niyam (type, value, kaun dega) banne ke baad badalta nahi: badalna ho to naya coupon banao."""
    return await service.admin_create(db, admin, request, body)


@router.get("", response_model=list[CouponAdminOut])
async def list_coupons(
    active: bool | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_list(db, active, limit, offset)


@router.get("/{coupon_id}", response_model=CouponAdminOut)
async def get_coupon(coupon_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.admin_get(db, coupon_id)


@router.patch("/{coupon_id}", response_model=CouponAdminOut)
async def update_coupon(
    coupon_id: uuid.UUID, body: CouponPatch, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)
):
    """Naam, band/chalu, tareekh, limit badalo. Karan zaroori, audit log banta hai. Coupon hatana nahi, band karna (is_active=false)."""
    return await service.admin_patch(db, admin, request, coupon_id, body)
