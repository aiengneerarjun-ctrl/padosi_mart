import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.checkout import CheckoutPreview
from app.services import checkout

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.get("/preview", response_model=CheckoutPreview)
async def preview(
    request: Request, address_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Order se pehle ka hisaab: dukaan-wise items, delivery charge, total. address_id na do to default address lagta hai."""
    return await checkout.preview(db, user, address_id, request.state.lang)