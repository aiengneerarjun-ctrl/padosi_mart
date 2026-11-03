import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.core.storage import public_url
from app.models import AuditLog, Seller, User
from app.models.seller import SellerStatus
from app.schemas.audit import AuditLogOut
from app.schemas.seller import AdminSellerOut, ReasonBody
from app.services import seller as seller_service

# Is router ke SAARE routes sirf Super Admin ke liye hain. Yahan router level par laga hai,
# taaki aage koi naya admin route banaye aur permission lagana bhool jaye to bhi khula na rahe.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_super_admin)])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _out(seller: Seller, phone: str) -> AdminSellerOut:
    return AdminSellerOut(
        id=seller.id,
        user_id=seller.user_id,
        phone=phone,
        seller_type=seller.seller_type,
        store_category=seller.store_category,
        store_image_medium_url=public_url(seller.store_image_key) if seller.store_image_key else None,
        business_name=seller.business_name,
        owner_name=seller.owner_name,
        status=seller.status,
        status_reason=seller.status_reason,
        created_at=seller.created_at,
    )


async def _with_phone(db: AsyncSession, seller: Seller) -> AdminSellerOut:
    user = await db.get(User, seller.user_id)
    return _out(seller, user.phone)


@router.get("/sellers", response_model=list[AdminSellerOut])
async def list_sellers(
    status: SellerStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(Seller, User.phone).join(User, User.id == Seller.user_id).order_by(Seller.created_at.desc())
    if status:
        q = q.where(Seller.status == status.value)
    rows = (await db.execute(q.limit(limit).offset(offset))).all()
    return [_out(s, phone) for s, phone in rows]


@router.post("/sellers/{seller_id}/approve", response_model=AdminSellerOut)
async def approve(seller_id: uuid.UUID, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await _with_phone(db, await seller_service.approve(db, admin, request, seller_id))


@router.post("/sellers/{seller_id}/reject", response_model=AdminSellerOut)
async def reject(seller_id: uuid.UUID, body: ReasonBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await _with_phone(db, await seller_service.reject(db, admin, request, seller_id, body.reason))


@router.post("/sellers/{seller_id}/suspend", response_model=AdminSellerOut)
async def suspend(seller_id: uuid.UUID, body: ReasonBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await _with_phone(db, await seller_service.suspend(db, admin, request, seller_id, body.reason))


@router.post("/sellers/{seller_id}/reactivate", response_model=AdminSellerOut)
async def reactivate(seller_id: uuid.UUID, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await _with_phone(db, await seller_service.reactivate(db, admin, request, seller_id))


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def audit_logs(
    target_type: str | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if target_type:
        q = q.where(AuditLog.target_type == target_type)
    return list(await db.scalars(q.limit(limit).offset(offset)))
