"""Delivery partner ki kamai.

- Har DELIVERED delivery par partner ko ek fixed rate milta hai. Rate Super Admin tay karta hai (ek global, aur free-delivery order ka alag).
  Rate delivery poori hote hi us delivery par likh diya jaata hai (deliveries.earning); baad me rate badle to purani kamai nahi badalti.
- Fail / released delivery par kamai nahi. Purani deliveries (jinme earning NULL hai) = 0.
- Admin partner ko paisa deta hai aur "paid" entry likhta hai (partner_payouts, badalta nahi). Dena baaki = kul kamai - kul paid.
  Paid kabhi kamai se zyada nahi; galti hui to negative sudhaar + note (cod_deposits jaisa).
- COD cash ka hisaab alag hai; kamai cash se nahi kategi.
Lock: partner row (deliver karte waqt bhi wahi lock hoti hai).
"""
import uuid
from decimal import Decimal

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Delivery, DeliveryPartner, DeliveryPaySettings, Order, PartnerPayout, User
from app.models.delivery import DeliveryStatus
from app.schemas.delivery_earnings import (
    AdminEarningsRowOut, EarningOut, EarningsSummaryOut, PayoutOut, RatesOut,
)
from app.services import notification
from app.services.audit import write_audit
from app.services.delivery_rules import deposit_problem, pick_rate

ZERO = Decimal("0.00")
RECENT = 20


async def _settings(db: AsyncSession, *, lock: bool = False) -> DeliveryPaySettings | None:
    q = select(DeliveryPaySettings).where(DeliveryPaySettings.id == 1).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    return await db.scalar(q)


async def earning_for(db: AsyncSession, order: Order) -> Decimal:
    """Is order ki delivery par partner ko ab kitna milega (abhi ka rate). Row na mile to 0."""
    s = await _settings(db)
    if s is None:
        return ZERO
    return pick_rate(order.delivery_fee, s.normal_rate, s.free_delivery_rate)


async def get_rates(db: AsyncSession) -> RatesOut:
    s = await _settings(db)
    if s is None:
        raise api_error(404, "NOT_FOUND", "Rate settings nahi mili.")
    return RatesOut(normal_rate=float(s.normal_rate), free_delivery_rate=float(s.free_delivery_rate), updated_at=s.updated_at)


async def set_rates(
    db: AsyncSession, admin: User, request: Request, normal_rate: Decimal | None, free_delivery_rate: Decimal | None, reason: str
) -> RatesOut:
    s = await _settings(db, lock=True)
    if s is None:
        raise api_error(404, "NOT_FOUND", "Rate settings nahi mili.")
    old = {"normal_rate": str(s.normal_rate), "free_delivery_rate": str(s.free_delivery_rate)}
    if normal_rate is not None:
        s.normal_rate = normal_rate
    if free_delivery_rate is not None:
        s.free_delivery_rate = free_delivery_rate
    s.updated_by = admin.id
    write_audit(
        db, actor=admin, action="delivery_earnings.set_rates", target_type="delivery_pay_settings", target_id="rates",
        old=old, new={"normal_rate": str(s.normal_rate), "free_delivery_rate": str(s.free_delivery_rate)}, reason=reason, request=request,
    )
    await db.commit()
    return await get_rates(db)


async def _totals(db: AsyncSession, partner_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    earned = await db.scalar(
        select(func.coalesce(func.sum(Delivery.earning), 0)).where(Delivery.partner_id == partner_id, Delivery.status == DeliveryStatus.DELIVERED)
    )
    paid = await db.scalar(select(func.coalesce(func.sum(PartnerPayout.amount), 0)).where(PartnerPayout.partner_id == partner_id))
    return Decimal(str(earned)), Decimal(str(paid))


async def summary(db: AsyncSession, partner_id: uuid.UUID) -> EarningsSummaryOut:
    earned, paid = await _totals(db, partner_id)
    rows = (
        await db.execute(
            select(Delivery.order_id, Order.order_no, Delivery.earning, Delivery.delivered_at)
            .join(Order, Order.id == Delivery.order_id)
            .where(Delivery.partner_id == partner_id, Delivery.status == DeliveryStatus.DELIVERED, Delivery.earning.is_not(None))
            .order_by(Delivery.delivered_at.desc())
            .limit(RECENT)
        )
    ).all()
    payouts = (
        await db.scalars(
            select(PartnerPayout).where(PartnerPayout.partner_id == partner_id).order_by(PartnerPayout.created_at.desc(), PartnerPayout.id).limit(RECENT)
        )
    ).all()
    return EarningsSummaryOut(
        total_earned=float(earned), total_paid=float(paid), due=float(earned - paid),
        recent_earnings=[EarningOut(order_id=r.order_id, order_number=f"PD{r.order_no}", amount=float(r.earning), delivered_at=r.delivered_at) for r in rows],
        recent_payouts=[PayoutOut(id=p.id, amount=float(p.amount), note=p.note, created_at=p.created_at) for p in payouts],
    )


async def my_summary(db: AsyncSession, user: User) -> EarningsSummaryOut:
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == user.id))
    if partner is None:
        raise api_error(403, "NOT_A_PARTNER", "Pehle delivery partner ke liye apply karo.")
    return await summary(db, partner.id)


async def admin_list(db: AsyncSession, include_settled: bool, limit: int, offset: int) -> list[AdminEarningsRowOut]:
    """Kis partner ko kitna dena baaki hai (sabse zyada pehle). Default: sirf jinka kuch baaki hai."""
    earn = (
        select(Delivery.partner_id.label("pid"), func.coalesce(func.sum(Delivery.earning), 0).label("e"))
        .where(Delivery.status == DeliveryStatus.DELIVERED)
        .group_by(Delivery.partner_id)
        .subquery()
    )
    pay = select(PartnerPayout.partner_id.label("pid"), func.sum(PartnerPayout.amount).label("p")).group_by(PartnerPayout.partner_id).subquery()
    paid = func.coalesce(pay.c.p, 0)
    q = (
        select(DeliveryPartner, User.phone, earn.c.e, paid)
        .join(User, User.id == DeliveryPartner.user_id)
        .join(earn, earn.c.pid == DeliveryPartner.id)
        .outerjoin(pay, pay.c.pid == DeliveryPartner.id)
        .order_by((earn.c.e - paid).desc(), DeliveryPartner.id)
        .limit(limit)
        .offset(offset)
    )
    if not include_settled:
        q = q.where(earn.c.e - paid > 0)
    return [
        AdminEarningsRowOut(
            partner_id=p.id, full_name=p.full_name, phone=phone, status=p.status,
            total_earned=float(e), total_paid=float(pd), due=float(Decimal(str(e)) - Decimal(str(pd))),
        )
        for p, phone, e, pd in (await db.execute(q)).all()
    ]


async def admin_detail(db: AsyncSession, partner_id: uuid.UUID) -> EarningsSummaryOut:
    if await db.get(DeliveryPartner, partner_id) is None:
        raise api_error(404, "PARTNER_NOT_FOUND", "Delivery partner nahi mila.")
    return await summary(db, partner_id)


async def record_payout(
    db: AsyncSession, admin: User, request: Request, partner_id: uuid.UUID, amount: Decimal, note: str | None
) -> EarningsSummaryOut:
    partner = await db.scalar(
        select(DeliveryPartner).where(DeliveryPartner.id == partner_id).with_for_update().execution_options(populate_existing=True)
    )
    if partner is None:
        raise api_error(404, "PARTNER_NOT_FOUND", "Delivery partner nahi mila.")
    earned, paid = await _totals(db, partner_id)
    problem = deposit_problem(earned, paid, amount)  # wahi niyam: paid kamai se zyada nahi, sudhaar paid se zyada nahi
    if problem == "EXCEEDS":
        raise api_error(409, "PAYOUT_EXCEEDS_DUE", "Itna paisa partner ka baaki nahi hai.")
    if problem == "BELOW_ZERO":
        raise api_error(409, "PAYOUT_CORRECTION_TOO_BIG", "Sudhaar ab tak diye hue paise se zyada nahi ho sakta.")
    db.add(PartnerPayout(partner_id=partner_id, amount=amount, note=note, recorded_by=admin.id))
    if amount > 0:  # NAYA: sudhaar (negative) par partner ko khabar nahi
        notification.add(db, partner.user_id, "PAYOUT_RECEIVED", {"amount": f"{amount:.2f}"})
    write_audit(
        db, actor=admin, action="delivery_earnings.payout", target_type="delivery_partner", target_id=partner_id,
        old={"due": str(earned - paid)}, new={"due": str(earned - paid - amount), "amount": str(amount)}, reason=note, request=request,
    )
    await db.commit()
    return await summary(db, partner_id)