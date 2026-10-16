from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.review import PartnerReviewsOut
from app.services import review as service

router = APIRouter(prefix="/delivery/reviews", tags=["delivery-reviews"])


@router.get("", response_model=PartnerReviewsOut)
async def my_reviews(
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Meri average rating aur customers ke reviews (customer ka naam nahi dikhta)."""
    return await service.partner_reviews(db, user, limit, offset)
