import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.support import MessageBody, TicketCreate, TicketDetailOut, TicketOut
from app.services import support as service

# Customer, seller aur delivery partner: sab apne support tickets yahin se (login wale user ke).
router = APIRouter(prefix="/support/tickets", tags=["support"])


@router.post("", response_model=TicketDetailOut, status_code=201)
async def create_ticket(body: TicketCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Naya ticket. raised_as = kis roop me (CUSTOMER / SELLER / DELIVERY_PARTNER). order_id optional (wo order tumhara hona chahiye)."""
    return await service.create(db, user, body)


@router.get("", response_model=list[TicketOut])
async def my_tickets(
    status: Literal["OPEN", "ANSWERED", "CLOSED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Mere tickets, jis par abhi haal me baat hui wo pehle."""
    return await service.list_mine(db, user, status, limit, offset)


@router.get("/{ticket_id}", response_model=TicketDetailOut)
async def get_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await service.get_mine(db, user, ticket_id)


@router.post("/{ticket_id}/messages", response_model=TicketDetailOut)
async def reply(ticket_id: uuid.UUID, body: MessageBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Ticket me aur likho. Band ticket me nahi (naya ticket kholo)."""
    return await service.reply_mine(db, user, ticket_id, body.body)


@router.post("/{ticket_id}/close", response_model=TicketDetailOut)
async def close_ticket(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Masla hal ho gaya: ticket band karo."""
    return await service.close_mine(db, user, ticket_id)
