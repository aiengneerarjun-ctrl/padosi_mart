"""Delivery partner ka COD cash ka hisaab.

- Delivery par partner customer se cash leta hai -> deliveries.cod_collected (delivery_progress me likha jaata hai).
- Partner admin ko cash jama karta hai -> admin "cash mila" likhta hai -> cod_deposits me ek row (bahi-khaata, badalta nahi).
- Partner ke paas cash = kul collected - kul jama. Jama kiya hua kabhi collected se zyada nahi ho sakta.
- Galti hui to naya negative entry (sudhaar) + note; purani row nahi chhedte.
- Partner suspended ho tab bhi cash jama ho sakta hai.
Lock: partner row (jo deliver karte waqt bhi lock hoti hai), taaki hisaab aur delivery ek saath na bigaden.
"""
import uuid
from decimal import Decimal

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import CodDeposit, Delivery, DeliveryPartner, Order, User
from app.models.delivery import DeliveryStatus
from app.schemas.delivery_cash import AdminCashRowOut, CashCollectionOut, CashDepositOut, CashSummaryOut
from app.services.audit import write_audit
from app.services.delivery_rules import deposit_problem

ZERO = Decimal("0.00")
RECENT = 20


async def _totals(db: AsyncSession, partner_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    collected = await db.scalar(
        select(func.coalesce(func.sum(Delivery.cod_collected), 0)).where(
            Delivery.partner_id == partner_id, Delivery.status == DeliveryStatus.DELIVERED
        )
    )
    deposited = await db.scalar(select(func.coalesce(func.sum(CodDeposit.amount), 0)).where(CodDeposit.partner_id == partner_id))
    return Decimal(str(collected)), Decimal(str(deposited))


async def summary(db: AsyncSession, partner_id: uuid.UUID) -> CashSummaryOut:
    collected, deposited = await _totals(db, partner_id)
    rows = (
        await db.execute(
            select(Delivery.order_id, Order.order_number, Delivery.cod_collected, Delivery.delivered_at)
            .join(Order, Order.id == Delivery.order_id)
            .where(Delivery.partner_id == partner_id, Delivery.status == DeliveryStatus.DELIVERED, Delivery.cod_collected > 0)
            .order_by(Delivery.delivered_at.desc())
            .limit(RECENT)
        )
    ).all()
    deposits = (
        await db.scalars(
            select(CodDeposit).where(CodDeposit.partner_id == partner_id).order_by(CodDeposit.created_at.desc(), CodDeposit.id).limit(RECENT)
        )
    ).all()
    return CashSummaryOut(
        cash_collected=float(collected), cash_deposited=float(deposited), cash_in_hand=float(collected - deposited),
        recent_collections=[
            CashCollectionOut(order_id=r.order_id, order_number=r.order_number, amount=float(r.cod_collected), delivered_at=r.delivered_at)
            for r in rows
        ],
        recent_deposits=[CashDepositOut(id=d.id, amount=float(d.amount), note=d.note, created_at=d.created_at) for d in deposits],
    )


async def my_summary(db: AsyncSession, user: User) -> CashSummaryOut:
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == user.id))
    if partner is None:
        raise api_error(403, "NOT_A_PARTNER", "Pehle delivery partner ke liye apply karo.")
    return await summary(db, partner.id)


async def admin_list(db: AsyncSession, include_settled: bool, limit: int, offset: int) -> list[AdminCashRowOut]:
    """Kis partner ke paas kitna cash hai (sabse zyada pehle). Default: sirf jinke paas cash baaki hai."""
    coll = (
        select(Delivery.partner_id.label("pid"), func.sum(Delivery.cod_collected).label("c"))
        .where(Delivery.status == DeliveryStatus.DELIVERED)
        .group_by(Delivery.partner_id)
        .subquery()
    )
    dep = select(CodDeposit.partner_id.label("pid"), func.sum(CodDeposit.amount).label("d")).group_by(CodDeposit.partner_id).subquery()
    deposited = func.coalesce(dep.c.d, 0)
    q = (
        select(DeliveryPartner, User.phone, coll.c.c, deposited)
        .join(User, User.id == DeliveryPartner.user_id)
        .join(coll, coll.c.pid == DeliveryPartner.id)
        .outerjoin(dep, dep.c.pid == DeliveryPartner.id)
        .order_by((coll.c.c - deposited).desc(), DeliveryPartner.id)
        .limit(limit)
        .offset(offset)
    )
    if not include_settled:
        q = q.where(coll.c.c - deposited > 0)
    return [
        AdminCashRowOut(
            partner_id=p.id, full_name=p.full_name, phone=phone, status=p.status,
            cash_collected=float(c), cash_deposited=float(d), cash_in_hand=float(Decimal(str(c)) - Decimal(str(d))),
        )
        for p, phone, c, d in (await db.execute(q)).all()
    ]


async def admin_detail(db: AsyncSession, partner_id: uuid.UUID) -> CashSummaryOut:
    if await db.get(DeliveryPartner, partner_id) is None:
        raise api_error(404, "PARTNER_NOT_FOUND", "Delivery partner nahi mila.")
    return await summary(db, partner_id)


async def record_deposit(
    db: AsyncSession, admin: User, request: Request, partner_id: uuid.UUID, amount: Decimal, note: str | None
) -> CashSummaryOut:
    partner = await db.scalar(
        select(DeliveryPartner).where(DeliveryPartner.id == partner_id).with_for_update().execution_options(populate_existing=True)
    )
    if partner is None:
        raise api_error(404, "PARTNER_NOT_FOUND", "Delivery partner nahi mila.")
    collected, deposited = await _totals(db, partner_id)
    problem = deposit_problem(collected, deposited, amount)
    if problem == "EXCEEDS":
        raise api_error(409, "DEPOSIT_EXCEEDS_CASH", "Itna cash partner ke paas nahi hai.")
    if problem == "BELOW_ZERO":
        raise api_error(409, "DEPOSIT_CORRECTION_TOO_BIG", "Sudhaar jama kiye hue cash se zyada nahi ho sakta.")
    db.add(CodDeposit(partner_id=partner_id, amount=amount, note=note, recorded_by=admin.id))
    write_audit(
        db, actor=admin, action="delivery_cash.deposit", target_type="delivery_partner", target_id=partner_id,
        old={"cash_in_hand": str(collected - deposited)}, new={"cash_in_hand": str(collected - deposited - amount), "amount": str(amount)},
        reason=note, request=request,
    )
    await db.commit()
    return await summary(db, partner_id)