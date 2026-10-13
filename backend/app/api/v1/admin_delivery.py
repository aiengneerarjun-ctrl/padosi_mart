import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.models.delivery import PartnerStatus
from app.schemas.delivery import AdminDeliveryPartnerOut, admin_partner_out
from app.schemas.seller import ReasonBody
from app.services import delivery_partner as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par, taaki koi naya route khula na rahe).
router = APIRouter(prefix="/admin/delivery-partners", tags=["admin-delivery"], dependencies=[Depends(require_super_admin)])

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("", response_model=list[AdminDeliveryPartnerOut])
async def list_partners(
    status: PartnerStatus | None = None, limit: Limit = 20, offset: Offset = 0, db: AsyncSession = Depends(get_db)
):
    rows = await service.list_partners(db, status.value if status else None, limit, offset)
    return [admin_partner_out(p, phone) for p, phone in rows]


@router.get("/{partner_id}", response_model=AdminDeliveryPartnerOut)
async def get_partner(partner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    partner, phone = await service.get_with_phone(db, partner_id)
    return admin_partner_out(partner, phone)


@router.post("/{partner_id}/approve", response_model=AdminDeliveryPartnerOut)
async def approve(partner_id: uuid.UUID, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return admin_partner_out(*await service.transition(db, admin, request, partner_id, "approve", None))


@router.post("/{partner_id}/reject", response_model=AdminDeliveryPartnerOut)
async def reject(partner_id: uuid.UUID, body: ReasonBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return admin_partner_out(*await service.transition(db, admin, request, partner_id, "reject", body.reason))


@router.post("/{partner_id}/suspend", response_model=AdminDeliveryPartnerOut)
async def suspend(partner_id: uuid.UUID, body: ReasonBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return admin_partner_out(*await service.transition(db, admin, request, partner_id, "suspend", body.reason))


@router.post("/{partner_id}/reactivate", response_model=AdminDeliveryPartnerOut)
async def reactivate(partner_id: uuid.UUID, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return admin_partner_out(*await service.transition(db, admin, request, partner_id, "reactivate", None))


@router.get("/{partner_id}/photos/{which}", response_class=Response)
async def kyc_photo(
    partner_id: uuid.UUID,
    which: Literal["id", "licence"],
    request: Request,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """KYC photo (private). Cache nahi hoti, aur har baar dekhne ka audit log banta hai."""
    data = await service.read_kyc_photo(db, admin, request, partner_id, which)
    return Response(
        content=data,
        media_type="image/webp",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )