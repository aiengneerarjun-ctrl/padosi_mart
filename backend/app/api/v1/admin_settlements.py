import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.settlement import (
    AdminSettlementRowOut, SellerPayoutBody, SettlementRateBody, SettlementSummaryOut,
)
from app.services import settlement as service
from app.core.errors import api_error

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/seller-settlements", tags=["admin-seller-settlements"], dependencies=[Depends(require_super_admin)])


@router.get("/rates")
async def retired_rates_get():
    """Legacy store-wide commission rates are retired; commissions are product-specific now."""
    raise api_error(410, "LEGACY_COMMISSION_DISABLED", "Store-wise commission band ho chuka hai. Product-wise commission use karein.")


@router.patch("/rates")
async def retired_rates_patch(body: SettlementRateBody):
    """Keep the legacy path authenticated, but never change the retired store-wide rates."""
    raise api_error(410, "LEGACY_COMMISSION_DISABLED", "Store-wise commission band ho chuka hai. Product-wise commission use karein.")


@router.get("", response_model=list[AdminSettlementRowOut])
async def dues(
    include_settled: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Kis seller ko kitna dena baaki hai (sabse zyada pehle). include_settled=true: jinka hisaab saaf hai wo bhi."""
    return await service.admin_list(db, include_settled, limit, offset)


@router.get("/{seller_id}", response_model=SettlementSummaryOut)
async def seller_settlement(seller_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.admin_detail(db, seller_id)


@router.post("/{seller_id}/payouts", response_model=SettlementSummaryOut, status_code=201)
async def record_payout(
    seller_id: uuid.UUID, body: SellerPayoutBody, request: Request,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    """Seller ko paisa diya (amount > 0, 'paid' entry). Galti sudhaar: amount < 0 + note. Paid kamai se zyada nahi ho sakta."""
    return await service.record_payout(db, admin, request, seller_id, body.amount, body.note)
