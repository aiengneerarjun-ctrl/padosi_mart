import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.payment import AdminRefundBody, ExpiredOut, PaymentDetailOut, RefundOut
from app.services import payment as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/payments", tags=["admin-payments"], dependencies=[Depends(require_super_admin)])


@router.get("/orders/{order_id}", response_model=PaymentDetailOut)
async def order_payment(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Is order ka payment aur uske saare refunds."""
    return await service.admin_detail(db, order_id)


@router.post("/orders/{order_id}/refunds", response_model=PaymentDetailOut, status_code=201)
async def refund_order(
    order_id: uuid.UUID, body: AdminRefundBody, request: Request,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    """Paid order ka paisa (poora ya hissa) wapas karo, jaise fail hui delivery me. Kul refund paid se zyada nahi ho sakta. Karan zaroori, audit log banta hai."""
    return await service.admin_refund(db, admin, request, order_id, body.amount, body.note)


@router.get("/refunds", response_model=list[RefundOut])
async def list_refunds(
    status: Literal["PENDING", "SUCCESS", "FAILED"] | None = "PENDING",
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Refunds (default: jo abhi PENDING hain)."""
    return await service.admin_list_refunds(db, status, limit, offset)


@router.post("/refunds/{refund_pk}/retry", response_model=RefundOut)
async def retry_refund(refund_pk: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Jo refund Cashfree ko nahi gaya (PENDING) use dobara bhejo."""
    return await service.admin_retry_refund(db, refund_pk)


@router.post("/expire-unpaid", response_model=ExpiredOut)
async def expire_unpaid(db: AsyncSession = Depends(get_db)):
    """Jin ONLINE orders ka payment samay par nahi hua unhe cancel karo (stock wapas). Cron isi ko (ya jobs/expire_unpaid.py) chalayega."""
    return ExpiredOut(expired=await service.expire_unpaid(db))