import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.delivery_earnings import AdminEarningsRowOut, EarningsSummaryOut, PayoutBody, RateBody, RatesOut
from app.services import delivery_earnings as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/delivery-earnings", tags=["admin-delivery-earnings"], dependencies=[Depends(require_super_admin)])


# NOTE: "/rates" ko "/{partner_id}" se pehle rakho (warna "rates" ko partner id samajh liya jaata).
@router.get("/rates", response_model=RatesOut)
async def get_rates(db: AsyncSession = Depends(get_db)):
    """Abhi ka partner kamai rate (normal aur free-delivery order ka)."""
    return await service.get_rates(db)


@router.patch("/rates", response_model=RatesOut)
async def set_rates(body: RateBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Rate badlo (jo bheja wahi badlega). Sirf aage ki deliveries par lagta hai. Karan zaroori, audit log banta hai."""
    return await service.set_rates(db, admin, request, body.normal_rate, body.free_delivery_rate, body.reason)


@router.get("", response_model=list[AdminEarningsRowOut])
async def dues(
    include_settled: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Kis partner ko kitna dena baaki hai (sabse zyada pehle). include_settled=true: jinka hisaab saaf hai wo bhi."""
    return await service.admin_list(db, include_settled, limit, offset)


@router.get("/{partner_id}", response_model=EarningsSummaryOut)
async def partner_earnings(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.admin_detail(db, partner_id)


@router.post("/{partner_id}/payouts", response_model=EarningsSummaryOut, status_code=201)
async def record_payout(
    partner_id: uuid.UUID, body: PayoutBody, request: Request,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    """Partner ko paisa diya (amount > 0, 'paid' entry). Galti sudhaar: amount < 0 + note. Paid kamai se zyada nahi ho sakta."""
    return await service.record_payout(db, admin, request, partner_id, body.amount, body.note)