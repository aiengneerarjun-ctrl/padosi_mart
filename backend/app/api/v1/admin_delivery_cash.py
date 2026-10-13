import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.delivery_cash import AdminCashRowOut, CashSummaryOut, DepositBody
from app.services import delivery_cash as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/delivery-cash", tags=["admin-delivery-cash"], dependencies=[Depends(require_super_admin)])


@router.get("", response_model=list[AdminCashRowOut])
async def cash_in_hand_list(
    include_settled: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Kis partner ke paas kitna COD cash hai (sabse zyada pehle). include_settled=true: jinka hisaab saaf hai wo bhi."""
    return await service.admin_list(db, include_settled, limit, offset)


@router.get("/{partner_id}", response_model=CashSummaryOut)
async def partner_cash(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.admin_detail(db, partner_id)


@router.post("/{partner_id}/deposits", response_model=CashSummaryOut, status_code=201)
async def record_deposit(
    partner_id: uuid.UUID, body: DepositBody, request: Request,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    """Partner ne cash jama kiya (amount > 0). Galti sudhaar: amount < 0 + note. Jama kiya hua cash partner ke paas ke cash se zyada nahi ho sakta."""
    return await service.record_deposit(db, admin, request, partner_id, body.amount, body.note)