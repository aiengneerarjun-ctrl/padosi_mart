import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.models.delivery import DeliveryStatus
from app.schemas.delivery_admin import AdminDeliveryOut, FailBody
from app.schemas.seller import ReasonBody
from app.services import delivery_admin as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/deliveries", tags=["admin-deliveries"], dependencies=[Depends(require_super_admin)])


@router.get("", response_model=list[AdminDeliveryOut])
async def list_deliveries(
    status: DeliveryStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """status na do to abhi chal rahi deliveries (sabse purani pehle, taaki atki hui dikhe)."""
    return await service.list_deliveries(db, status.value if status else None, limit, offset)


@router.post("/{order_id}/release", response_model=AdminDeliveryOut)
async def release(order_id: uuid.UUID, body: ReasonBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Pickup se pehle partner se order wapas lo (wo nazdeek ke partners ko phir dikhega). Saaman uth chuka ho to 409 GOODS_IN_HAND."""
    return await service.release(db, admin, request, order_id, body.reason)


@router.post("/{order_id}/fail", response_model=AdminDeliveryOut)
async def fail(order_id: uuid.UUID, body: FailBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Partner ke paas saaman hai par delivery nahi ho sakti: order FAILED_DELIVERY, partner free."""
    return await service.fail(db, admin, request, order_id, body.reason_code, body.note)


@router.post("/{order_id}/unlock-otp", response_model=AdminDeliveryOut)
async def unlock_otp(order_id: uuid.UUID, body: ReasonBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Galat OTP se band delivery ko dobara koshish ke liye kholo."""
    return await service.unlock_otp(db, admin, request, order_id, body.reason)