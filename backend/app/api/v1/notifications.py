import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.notification import MarkedOut, NotificationOut, UnreadCountOut
from app.services import notification as service

# Customer, seller aur delivery partner: sab apni hi notifications dekhte hain (login wale user ki).
router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def my_notifications(
    request: Request, unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Meri notifications (naya pehle), meri bhasha me."""
    return await service.list_mine(db, user, unread_only, limit, offset, request.state.lang)


# NOTE: "/unread-count" aur "/read-all" ko "/{notification_id}/read" se pehle rakho.
@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Kitni notifications padhi nahi (app ke ghanti ke nishaan ke liye)."""
    return UnreadCountOut(unread=await service.unread_count(db, user))


@router.post("/read-all", response_model=MarkedOut)
async def read_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return MarkedOut(marked=await service.mark_all_read(db, user))


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def read_one(notification_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service.mark_read(db, user, notification_id, request.state.lang)