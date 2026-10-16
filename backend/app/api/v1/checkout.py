import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.checkout import CheckoutPreview
from app.services import checkout

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.get("/preview", response_model=CheckoutPreview)
async def preview(
    request: Request, address_id: uuid.UUID | None = None, coupon_code: str | None = Query(default=None, max_length=20),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Order se pehle ka hisaab: dukaan-wise items, delivery charge, coupon discount, total.
    address_id na do to default address lagta hai. coupon_code do to discount dikhta hai; coupon na chale to coupon_error me karan aata hai."""
    return await checkout.preview(db, user, address_id, request.state.lang, coupon_code)
