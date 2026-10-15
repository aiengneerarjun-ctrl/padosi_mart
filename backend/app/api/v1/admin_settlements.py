import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.settlement import (
    AdminSettlementRowOut, SellerPayoutBody, SettlementRateBody, SettlementRatesOut, SettlementSummaryOut,
)
from app.services import settlement as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/seller-settlements", tags=["admin-seller-settlements"], dependencies=[Depends(require_super_admin)])


# NOTE: "/rates" ko "/{seller_id}" se pehle rakho (warna "rates" ko seller id samajh liya jaata).
@router.get("/rates", response_model=SettlementRatesOut)
async def get_rates(db: AsyncSession = Depends(get_db)):
    """Abhi ka commission (percent): kirana aur restaurant ka."""
    return await service.get_rates(db)


@router.patch("/rates", response_model=SettlementRatesOut)
async def set_rates(body: SettlementRateBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Commission badlo (jo bheja wahi badlega). Sirf aage ki deliveries par lagta hai. Karan zaroori, audit log banta hai."""
    return await service.set_rates(db, admin, request, body.kirana_rate, body.restaurant_rate, body.reason)


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