"""Super Admin ke delivery tools: atke hue order ko nikalna.

- list: abhi chal rahi deliveries (sabse purani pehle, taaki atki hui dikhe) ya kisi status ki.
- release: pickup se pehle partner se order wapas lena (partner gayab / jawab nahi de raha). Order wapas nazdeek ke partners ko dikhta hai.
- fail: partner ke paas saaman hai par delivery nahi ho sakti (accident, partner gayab, customer nahi mila). Order FAILED_DELIVERY.
- unlock-otp: galat OTP se band delivery khulwana.
Har kaam ka audit log. Lock ka kram wahi: partner row, phir Order row.
"""
import uuid
from datetime import datetime

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Delivery, DeliveryPartner, Order, User
from app.models.delivery import DeliveryStatus
from app.schemas.delivery_admin import AdminDeliveryOut
from app.services.audit import write_audit
from app.services.delivery_assignment import _load_order, _release
from app.services.delivery_progress import mark_failed
from app.services.delivery_rules import ACTIVE_DELIVERY_STATUSES, goods_in_hand


def _row(d: Delivery, order_number: str, order_status: str, p: DeliveryPartner, phone: str, now: datetime) -> AdminDeliveryOut:
    return AdminDeliveryOut(
        delivery_id=d.id, order_id=d.order_id, order_number=f"PD{order_number}", order_status=order_status, partner_id=p.id,
        partner_name=p.full_name, partner_phone=phone, status=d.status, assigned_at=d.assigned_at, delivered_at=d.delivered_at,
        failed_at=d.failed_at, fail_reason=d.fail_reason, otp_locked=d.otp_locked_until is not None and d.otp_locked_until > now,
        cod_collected=float(d.cod_collected) if d.cod_collected is not None else None,
    )


def _query():
    return (
        select(Delivery, Order.order_no, Order.status, DeliveryPartner, User.phone)
        .join(Order, Order.id == Delivery.order_id)
        .join(DeliveryPartner, DeliveryPartner.id == Delivery.partner_id)
        .join(User, User.id == DeliveryPartner.user_id)
    )


async def list_deliveries(db: AsyncSession, status: str | None, limit: int, offset: int) -> list[AdminDeliveryOut]:
    """status na do to abhi chal rahi (ASSIGNED / PICKED_UP / OUT_FOR_DELIVERY), sabse purani pehle."""
    now = await db.scalar(select(func.now()))
    q = _query()
    if status:
        q = q.where(Delivery.status == status).order_by(Delivery.assigned_at.desc(), Delivery.id)
    else:
        q = q.where(Delivery.status.in_(ACTIVE_DELIVERY_STATUSES)).order_by(Delivery.assigned_at, Delivery.id)
    rows = (await db.execute(q.limit(limit).offset(offset).execution_options(populate_existing=True))).all()
    return [_row(d, num, ost, p, phone, now) for d, num, ost, p, phone in rows]


async def _one(db: AsyncSession, delivery_id: uuid.UUID) -> AdminDeliveryOut:
    now = await db.scalar(select(func.now()))
    d, num, ost, p, phone = (await db.execute(_query().where(Delivery.id == delivery_id).execution_options(populate_existing=True))).one()
    return _row(d, num, ost, p, phone, now)


async def _lock_live(db: AsyncSession, order_id: uuid.UUID) -> tuple[Delivery, Order]:
    """Order ki chalti delivery: pehle uska partner row lock, phir Order row lock (baaki sab jagah wahi kram)."""
    partner_id = await db.scalar(
        select(Delivery.partner_id).where(Delivery.order_id == order_id, Delivery.status.in_(ACTIVE_DELIVERY_STATUSES))
    )
    if partner_id is None:
        raise api_error(404, "DELIVERY_NOT_FOUND", "Is order ki koi chalti delivery nahi hai.")
    await db.scalar(select(DeliveryPartner.id).where(DeliveryPartner.id == partner_id).with_for_update())
    delivery = await db.scalar(  # lock ke intezar me badal gayi ho to taaza dekho
        select(Delivery).where(Delivery.order_id == order_id, Delivery.status.in_(ACTIVE_DELIVERY_STATUSES)).execution_options(populate_existing=True)
    )
    if delivery is None:
        raise api_error(404, "DELIVERY_NOT_FOUND", "Is order ki koi chalti delivery nahi hai.")
    order = await _load_order(db, order_id, lock=True)
    return delivery, order


async def release(db: AsyncSession, admin: User, request: Request, order_id: uuid.UUID, reason: str) -> AdminDeliveryOut:
    delivery, order = await _lock_live(db, order_id)
    if goods_in_hand(delivery.status, [s.status for s in order.store_orders]):
        raise api_error(409, "GOODS_IN_HAND", "Partner ke paas saaman hai, order chhudwa nahi sakte; delivery fail karo.")
    old = {"delivery": str(delivery.status), "order": str(order.status)}
    _release(db, delivery, order, actor=admin, role="SUPER_ADMIN", reason=f"admin ne wapas liya: {reason}"[:190])
    write_audit(db, actor=admin, action="delivery.admin_release", target_type="order", target_id=order.id,
                old=old, new={"delivery": str(delivery.status), "order": str(order.status)}, reason=reason, request=request)
    delivery_id = delivery.id
    await db.commit()
    return await _one(db, delivery_id)


async def fail(db: AsyncSession, admin: User, request: Request, order_id: uuid.UUID, code: str, note: str | None) -> AdminDeliveryOut:
    delivery, order = await _lock_live(db, order_id)
    if not goods_in_hand(delivery.status, [s.status for s in order.store_orders]):
        raise api_error(409, "NOTHING_PICKED_UP", "Abhi saaman nahi uthaya hai, order wapas lo (release).")
    old = {"delivery": str(delivery.status), "order": str(order.status)}
    text = mark_failed(db, delivery, order, actor=admin, role="SUPER_ADMIN", code=code, note=note)
    write_audit(db, actor=admin, action="delivery.admin_fail", target_type="order", target_id=order.id,
                old=old, new={"delivery": str(delivery.status), "order": str(order.status)}, reason=text, request=request)
    delivery_id = delivery.id
    await db.commit()
    return await _one(db, delivery_id)


async def unlock_otp(db: AsyncSession, admin: User, request: Request, order_id: uuid.UUID, reason: str) -> AdminDeliveryOut:
    delivery, order = await _lock_live(db, order_id)
    if delivery.status != DeliveryStatus.OUT_FOR_DELIVERY:
        raise api_error(409, "INVALID_STATE", "Abhi ki halat me ye kaam nahi ho sakta.")
    delivery.otp_attempts = 0
    delivery.otp_locked_until = None
    write_audit(db, actor=admin, action="delivery.unlock_otp", target_type="order", target_id=order.id, reason=reason, request=request)
    delivery_id = delivery.id
    await db.commit()
    return await _one(db, delivery_id)