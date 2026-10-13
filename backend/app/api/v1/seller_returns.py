import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models import Seller, User
from app.schemas.delivery_return import ReceiveBody, ReturnOut
from app.services import delivery_return as service

router = APIRouter(prefix="/seller/returns", tags=["seller-returns"])


@router.get("", response_model=list[ReturnOut])
async def my_returns(
    request: Request, status: Literal["PENDING", "RECEIVED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db),
):
    """Fail hui deliveries ka saaman jo meri dukaan ko wapas milna hai (status=PENDING se sirf baaki wale)."""
    return await service.seller_list(db, seller, status, limit, offset, request.state.lang)


@router.post("/{store_order_id}/received", response_model=ReturnOut)
async def received(
    store_order_id: uuid.UUID, body: ReceiveBody, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Saaman wapas mil gaya. stock_ok=true (kirana) me stock wapas judta hai; kharab saaman ho to stock_ok=false bhejo."""
    return await service.receive(db, user, store_order_id, stock_ok=body.stock_ok, note=body.note, lang=request.state.lang, seller=seller)