"""Support tickets: customer / seller / delivery partner Super Admin ko likhte hain, jawab ticket me hi aata hai.

Niyam (owner ke "ek hi admin" wale faisle ke hisaab se):
- Koi bhi login user ticket khol sakta hai, apne role (raised_as) me; wo role uske paas hona chahiye. Order jodna ho to wo order uska apna hona chahiye
  (customer ka order / seller ke dukaan wala order / partner ki delivery); doosre ka order 404.
- Ek user ke ek saath 5 se zyada khule (CLOSED nahi) ticket nahi (spam rokne ke liye). Ek ticket me zyada se zyada 100 sandesha.
- Status: OPEN = support ke jawab ka intezaar, ANSWERED = support ne jawab diya (user ka intezaar), CLOSED. User jawab de to wapas OPEN.
- CLOSED ticket me jawab nahi; user naya ticket khole. Admin chahe to dobara kholega (reopen).
- User sirf apna ticket dekhta hai (doosre ka 404). Sandesha bhejne ke baad badalta / hatta nahi (database trigger).
- Admin ke jawab / ticket band hone par user ko notification milti hai (inbox + push).
- Ticket band / dobara khulna audit log me jata hai.
"""
import uuid
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Delivery, DeliveryPartner, Order, Seller, StoreOrder, SupportMessage, SupportTicket, User
from app.schemas.support import (
    AdminTicketDetailOut, AdminTicketOut, TicketCreate, TicketDetailOut, TicketMessageOut, TicketOut,
)
from app.services import notification
from app.services.audit import write_audit

MAX_OPEN_TICKETS = 5
MAX_MESSAGES = 100
PREVIEW_CHARS = 100
ROLES_FOR = {"CUSTOMER": {"CUSTOMER"}, "SELLER": {"SELLER", "RESTAURANT"}, "DELIVERY_PARTNER": {"DELIVERY_PARTNER"}}


def has_role(role_names: list[str] | set[str], raised_as: str) -> bool:
    return bool(set(role_names) & ROLES_FOR.get(raised_as, set()))


def preview(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"


# ---------- output banana ----------

async def _out(db: AsyncSession, tickets: list[SupportTicket], *, with_messages: bool = False, admin: bool = False) -> list:
    if not tickets:
        return []
    ids = [t.id for t in tickets]
    counts = dict((await db.execute(select(SupportMessage.ticket_id, func.count()).where(SupportMessage.ticket_id.in_(ids)).group_by(SupportMessage.ticket_id))).all())
    last = dict(
        (
            await db.execute(
                select(SupportMessage.ticket_id, SupportMessage.body).distinct(SupportMessage.ticket_id)
                .where(SupportMessage.ticket_id.in_(ids)).order_by(SupportMessage.ticket_id, SupportMessage.created_at.desc(), SupportMessage.id.desc())
            )
        ).all()
    )
    order_ids = {t.order_id for t in tickets if t.order_id}
    order_no = dict((await db.execute(select(Order.id, Order.order_no).where(Order.id.in_(order_ids)))).all()) if order_ids else {}
    messages: dict = {}
    if with_messages:
        for m in await db.scalars(select(SupportMessage).where(SupportMessage.ticket_id.in_(ids)).order_by(SupportMessage.created_at, SupportMessage.id)):
            messages.setdefault(m.ticket_id, []).append(TicketMessageOut(id=m.id, author_type=m.author_type, body=m.body, created_at=m.created_at))
    users = {}
    if admin:
        users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({t.user_id for t in tickets})))}

    out = []
    for t in tickets:
        base = dict(
            id=t.id, ticket_number=t.ticket_number, raised_as=t.raised_as, category=t.category, subject=t.subject, status=t.status,
            order_id=t.order_id, order_number=f"PD{order_no[t.order_id]}" if t.order_id in order_no else None,
            last_message=preview(last.get(t.id, "")), message_count=counts.get(t.id, 0), created_at=t.created_at,
            last_message_at=t.last_message_at, closed_at=t.closed_at,
        )
        if admin:
            u = users[t.user_id]
            extra = dict(user_id=u.id, user_name=u.name, user_phone=u.phone)
            out.append(AdminTicketDetailOut(**base, **extra, messages=messages.get(t.id, [])) if with_messages else AdminTicketOut(**base, **extra))
        else:
            out.append(TicketDetailOut(**base, messages=messages.get(t.id, [])) if with_messages else TicketOut(**base))
    return out


async def _load(db: AsyncSession, ticket_id: uuid.UUID, *, user: User | None = None, lock: bool = False) -> SupportTicket:
    q = select(SupportTicket).where(SupportTicket.id == ticket_id).execution_options(populate_existing=True)
    if user is not None:
        q = q.where(SupportTicket.user_id == user.id)  # doosre ka ticket bhi 404
    if lock:
        q = q.with_for_update()
    t = await db.scalar(q)
    if t is None:
        await db.rollback()
        raise api_error(404, "TICKET_NOT_FOUND", "Ticket nahi mila.")
    return t


# ---------- User (customer / seller / partner) ----------

async def _check_order(db: AsyncSession, user: User, raised_as: str, order_id: uuid.UUID) -> None:
    if raised_as == "CUSTOMER":
        ok = await db.scalar(select(Order.id).where(Order.id == order_id, Order.user_id == user.id))
    elif raised_as == "SELLER":
        ok = await db.scalar(
            select(StoreOrder.id).join(Seller, Seller.id == StoreOrder.seller_id).where(StoreOrder.order_id == order_id, Seller.user_id == user.id).limit(1)
        )
    else:
        ok = await db.scalar(
            select(Delivery.id).join(DeliveryPartner, DeliveryPartner.id == Delivery.partner_id)
            .where(Delivery.order_id == order_id, DeliveryPartner.user_id == user.id).limit(1)
        )
    if ok is None:
        await db.rollback()
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")


async def create(db: AsyncSession, user: User, body: TicketCreate) -> TicketDetailOut:
    if not has_role(user.role_names, body.raised_as):
        raise api_error(403, "TICKET_ROLE_NOT_ALLOWED", "Is roop me ticket nahi khol sakte.")
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())  # ek user ke do ticket ek saath khule to ginti sahi rahe
    open_now = await db.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.user_id == user.id, SupportTicket.status != "CLOSED"))
    if (open_now or 0) >= MAX_OPEN_TICKETS:
        await db.rollback()
        raise api_error(409, "TICKET_LIMIT", "Bahut saare ticket khule hain.")
    if body.order_id is not None:
        await _check_order(db, user, body.raised_as, body.order_id)
    t = SupportTicket(user_id=user.id, raised_as=body.raised_as, order_id=body.order_id, category=body.category, subject=body.subject)
    db.add(t)
    await db.flush()
    db.add(SupportMessage(ticket_id=t.id, author_id=user.id, author_type="USER", body=body.message))
    await db.commit()
    return await get_mine(db, user, t.id)


async def list_mine(db: AsyncSession, user: User, status: str | None, limit: int, offset: int) -> list[TicketOut]:
    q = select(SupportTicket).where(SupportTicket.user_id == user.id)
    if status:
        q = q.where(SupportTicket.status == status)
    tickets = (await db.scalars(q.order_by(SupportTicket.last_message_at.desc(), SupportTicket.id).limit(limit).offset(offset))).all()
    return await _out(db, list(tickets))


async def get_mine(db: AsyncSession, user: User, ticket_id: uuid.UUID) -> TicketDetailOut:
    t = await _load(db, ticket_id, user=user)
    return (await _out(db, [t], with_messages=True))[0]


async def _add_message(db: AsyncSession, t: SupportTicket, author: User, author_type: str, body: str) -> None:
    if t.status == "CLOSED":
        await db.rollback()
        raise api_error(409, "TICKET_CLOSED", "Ye ticket band hai.")
    if (await db.scalar(select(func.count()).select_from(SupportMessage).where(SupportMessage.ticket_id == t.id)) or 0) >= MAX_MESSAGES:
        await db.rollback()
        raise api_error(409, "TICKET_MESSAGE_LIMIT", "Is ticket me bahut sandesha ho gaye.")
    db.add(SupportMessage(ticket_id=t.id, author_id=author.id, author_type=author_type, body=body))
    t.status = "OPEN" if author_type == "USER" else "ANSWERED"
    t.last_message_at = datetime.now(timezone.utc)


async def reply_mine(db: AsyncSession, user: User, ticket_id: uuid.UUID, body: str) -> TicketDetailOut:
    t = await _load(db, ticket_id, user=user, lock=True)
    await _add_message(db, t, user, "USER", body)
    await db.commit()
    return await get_mine(db, user, ticket_id)


async def close_mine(db: AsyncSession, user: User, ticket_id: uuid.UUID) -> TicketDetailOut:
    """"Mera masla hal ho gaya": user khud ticket band kar sakta hai. Pehle se band ho to wahi haal (error nahi)."""
    t = await _load(db, ticket_id, user=user, lock=True)
    if t.status != "CLOSED":
        t.status = "CLOSED"
        t.closed_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_mine(db, user, ticket_id)


# ---------- Admin ----------

async def admin_list(db: AsyncSession, status: str | None, raised_as: str | None, limit: int, offset: int) -> list[AdminTicketOut]:
    q = select(SupportTicket)
    if status:
        q = q.where(SupportTicket.status == status)
    if raised_as:
        q = q.where(SupportTicket.raised_as == raised_as)
    priority = case((SupportTicket.status == "OPEN", 0), (SupportTicket.status == "ANSWERED", 1), else_=2)
    waiting_since = case((SupportTicket.status == "OPEN", SupportTicket.last_message_at))  # khule ticket: sabse purana intezaar pehle
    q = q.order_by(priority, waiting_since.asc().nulls_last(), SupportTicket.last_message_at.desc(), SupportTicket.id).limit(limit).offset(offset)
    return await _out(db, list((await db.scalars(q)).all()), admin=True)


async def admin_get(db: AsyncSession, ticket_id: uuid.UUID) -> AdminTicketDetailOut:
    t = await _load(db, ticket_id)
    return (await _out(db, [t], with_messages=True, admin=True))[0]


async def admin_reply(db: AsyncSession, admin: User, ticket_id: uuid.UUID, body: str) -> AdminTicketDetailOut:
    t = await _load(db, ticket_id, lock=True)
    await _add_message(db, t, admin, "ADMIN", body)
    notification.add(db, t.user_id, "TICKET_REPLIED", {"ticket_no": t.ticket_number}, t.order_id)
    await db.commit()
    return await admin_get(db, ticket_id)


async def admin_close(db: AsyncSession, admin: User, request: Request, ticket_id: uuid.UUID, note: str | None) -> AdminTicketDetailOut:
    t = await _load(db, ticket_id, lock=True)
    if t.status != "CLOSED":  # dobara band karna: kuch nahi badalta
        old = t.status
        t.status = "CLOSED"
        t.closed_at = datetime.now(timezone.utc)
        write_audit(db, actor=admin, action="support.close", target_type="support_ticket", target_id=t.id, old={"status": old}, new={"status": "CLOSED"}, reason=note, request=request)
        notification.add(db, t.user_id, "TICKET_CLOSED", {"ticket_no": t.ticket_number}, t.order_id)
    await db.commit()
    return await admin_get(db, ticket_id)


async def admin_reopen(db: AsyncSession, admin: User, request: Request, ticket_id: uuid.UUID, note: str | None) -> AdminTicketDetailOut:
    t = await _load(db, ticket_id, lock=True)
    if t.status == "CLOSED":
        t.status = "OPEN"
        t.closed_at = None
        t.last_message_at = datetime.now(timezone.utc)
        write_audit(db, actor=admin, action="support.reopen", target_type="support_ticket", target_id=t.id, old={"status": "CLOSED"}, new={"status": "OPEN"}, reason=note, request=request)
    await db.commit()
    return await admin_get(db, ticket_id)
