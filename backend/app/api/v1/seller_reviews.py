import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller
from app.core.database import get_db
from app.models import Seller
from app.schemas.review import SellerReviewsOut
from app.services import review as service

router = APIRouter(prefix="/seller/reviews", tags=["seller-reviews"])


@router.get("", response_model=SellerReviewsOut)
async def my_reviews(
    request: Request, store_id: uuid.UUID | None = None, max_rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db),
):
    """Meri dukaanon ke reviews aur average. store_id se ek dukaan, max_rating=2 se sirf kam rating wale."""
    return await service.seller_reviews(db, seller, store_id, max_rating, limit, offset, request.state.lang)
