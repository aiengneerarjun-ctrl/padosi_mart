import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models import User
from app.schemas.support import AdminTicketDetailOut, AdminTicketOut, CloseBody, MessageBody
from app.services import support as service

# Is router ke SAARE routes sirf Super Admin ke liye (router level par).
router = APIRouter(prefix="/admin/support/tickets", tags=["admin-support"], dependencies=[Depends(require_super_admin)])


@router.get("", response_model=list[AdminTicketOut])
async def list_tickets(
    status: Literal["OPEN", "ANSWERED", "CLOSED"] | None = None,
    raised_as: Literal["CUSTOMER", "SELLER", "DELIVERY_PARTNER"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    """Support queue: jawab ke intezaar wale (OPEN) pehle, sabse purana intezaar sabse upar; phir ANSWERED, phir CLOSED."""
    return await service.admin_list(db, status, raised_as, limit, offset)


@router.get("/{ticket_id}", response_model=AdminTicketDetailOut)
async def get_ticket(ticket_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.admin_get(db, ticket_id)


@router.post("/{ticket_id}/messages", response_model=AdminTicketDetailOut)
async def reply(ticket_id: uuid.UUID, body: MessageBody, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    """Jawab do. User ko notification jati hai, ticket ANSWERED ho jata hai."""
    return await service.admin_reply(db, admin, ticket_id, body.body)


@router.post("/{ticket_id}/close", response_model=AdminTicketDetailOut)
async def close_ticket(
    ticket_id: uuid.UUID, request: Request, body: CloseBody | None = None,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    return await service.admin_close(db, admin, request, ticket_id, body.note if body else None)


@router.post("/{ticket_id}/reopen", response_model=AdminTicketDetailOut)
async def reopen_ticket(
    ticket_id: uuid.UUID, request: Request, body: CloseBody | None = None,
    admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db),
):
    return await service.admin_reopen(db, admin, request, ticket_id, body.note if body else None)
