import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.review import AdminReviewOut, HideBody
from app.services import review as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/reviews", tags=["admin-reviews"], dependencies=[Depends(require_super_admin)])


@router.get("", response_model=list[AdminReviewOut])
async def list_reviews(
    status: Literal["VISIBLE", "HIDDEN"] | None = None, target: Literal["STORE", "PARTNER"] | None = None,
    max_rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Saare reviews (naya pehle). max_rating=2 se kam rating wale, status=HIDDEN se chhupaye hue."""
    return await service.admin_list(db, status, target, max_rating, limit, offset)


@router.post("/{review_id}/hide", response_model=AdminReviewOut)
async def hide_review(review_id: uuid.UUID, body: HideBody, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Review chhupao (karan zaroori, audit log banta hai). Average se bhi hat jata hai. Dobara bhejna theek hai."""
    return await service.hide(db, admin, request, review_id, body.reason)


@router.post("/{review_id}/unhide", response_model=AdminReviewOut)
async def unhide_review(review_id: uuid.UUID, request: Request, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    return await service.unhide(db, admin, request, review_id)
