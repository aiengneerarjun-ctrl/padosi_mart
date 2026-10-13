import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.delivery_return import AdminReceiveBody, ReturnOut
from app.services import delivery_return as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/returns", tags=["admin-returns"], dependencies=[Depends(require_super_admin)])


@router.get("", response_model=list[ReturnOut])
async def list_returns(
    request: Request, status: Literal["PENDING", "RECEIVED"] | None = "PENDING",
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Kis dukaan ko fail hui delivery ka saaman wapas milna baaki hai (sabse purana pehle)."""
    return await service.admin_list(db, status, limit, offset, request.state.lang)


@router.post("/{store_order_id}/received", response_model=ReturnOut)
async def received(
    store_order_id: uuid.UUID, body: AdminReceiveBody, request: Request,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    """Seller jawab nahi de raha ya suspended hai: admin dukaan ki jagah "saaman wapas mila" likhta hai (audit log banta hai)."""
    return await service.receive(db, admin, store_order_id, stock_ok=body.stock_ok, note=body.note, lang=request.state.lang, request=request)