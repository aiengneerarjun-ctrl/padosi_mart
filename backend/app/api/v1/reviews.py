import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.review import ReviewableOut, ReviewCreate, ReviewOut, StoreReviewsOut
from app.services import review as service

# Customer: review dena / dekhna, aur dukaan ke public reviews.
router = APIRouter(tags=["reviews"])


@router.get("/orders/{order_id}/reviewable", response_model=ReviewableOut)
async def reviewable(order_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Is order me kis-kis ka review de sakte hain (dukaan / delivery partner), kaun sa ho chuka, aur kab tak de sakte hain."""
    return await service.reviewable(db, user, order_id, request.state.lang)


@router.post("/reviews", response_model=ReviewOut, status_code=201)
async def create_review(body: ReviewCreate, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delivery ke 7 din tak dukaan (target=STORE + store_id) ya delivery partner (target=PARTNER) ka review. Ek cheez ka ek hi baar."""
    return await service.create(db, user, body, request.state.lang)


@router.get("/reviews/mine", response_model=list[ReviewOut])
async def my_reviews(
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await service.my_reviews(db, user, limit, offset)


@router.get("/shop/stores/{store_id}/reviews", response_model=StoreReviewsOut)
async def store_reviews(
    store_id: uuid.UUID, request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Dukaan ki average rating (star-wise ginti ke saath) aur uske reviews, naya pehle."""
    return await service.store_reviews(db, store_id, limit, offset, request.state.lang)
