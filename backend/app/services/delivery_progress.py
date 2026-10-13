"""Delivery ka aage ka safar: dukaan se pickup -> out for delivery -> delivered (OTP se).

- Har dukaan se alag "uthaya" (PICKED_UP) mark hota hai, aur sirf tab jab seller ne us dukaan ko READY_FOR_PICKUP kiya ho.
- Saari (active) dukaanon se uth jaye to Delivery aur Order dono PICKED_UP.
- Phir partner "ghar ke liye nikla" (start) karta hai -> OUT_FOR_DELIVERY. Customer ko tab apne order me 4 ank ka OTP dikhta hai.
- Customer se OTP lekar partner deliver karta hai -> DELIVERED. COD me cash mil gaya maana jaata hai: payment_status PAID,
  aur kitna liya wo deliveries.cod_collected me likha jaata hai (cash ka hisaab alag step me aayega).
- 5 galat OTP ke baad 10 minute ke liye band (429 OTP_LOCKED).
- Pickup shuru hone ke baad order chhod nahi sakte, aur partner offline nahi ho sakta.
Lock ka kram wahi: pehle partner row, phir Order row.
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import api_error
from app.models import Delivery, Order, User
from app.models.delivery import DeliveryStatus, PartnerStatus
from app.models.order import OrderStatus, PaymentStatus, StoreOrderStatus
from app.schemas.delivery_assignment import DeliveredOut, MyDeliveryOut
from app.services.delivery_assignment import (
    INACTIVE_STORE,
    _history,
    _load_order,
    _my_delivery,
    _my_live_delivery,
    _partner_for,
)
from app.services.delivery_rules import (
    OTP_LOCK_SECONDS,
    OTP_MAX_ATTEMPTS,
    all_stores_picked_up,
    can_pickup_store,
    cod_amount_due,
    otp_matches,
)


def _require_active(partner) -> None:
    if partner.status != PartnerStatus.ACTIVE:
        raise api_error(403, "PARTNER_NOT_ACTIVE", "Aapka delivery partner account abhi active nahi hai.")


async def _live_for_order(db: AsyncSession, user: User, order_id: uuid.UUID) -> Delivery:
    partner = await _partner_for(db, user, lock=True)
    _require_active(partner)
    delivery = await _my_live_delivery(db, partner.id, order_id)
    if delivery is None:
        raise api_error(404, "DELIVERY_NOT_FOUND", "Aapke paas ye delivery nahi hai (ya pickup ho chuka hai).")
    return delivery


async def pickup_store(db: AsyncSession, user: User, order_id: uuid.UUID, store_order_id: uuid.UUID, lang: str) -> MyDeliveryOut:
    delivery = await _live_for_order(db, user, order_id)
    order: Order = await _load_order(db, order_id, lock=True)
    so = next((s for s in order.store_orders if s.id == store_order_id and s.status not in INACTIVE_STORE), None)
    if so is None:
        raise api_error(404, "STORE_PART_NOT_FOUND", "Is order me ye dukaan nahi hai.")
    if so.status == StoreOrderStatus.PICKED_UP:  # wahi dobara: kuch nahi badalta (app retry safe)
        return _my_delivery(delivery, order, lang)
    if delivery.status != DeliveryStatus.ASSIGNED:
        raise api_error(409, "INVALID_STATE", "Abhi ki halat me ye kaam nahi ho sakta.")
    if not can_pickup_store(so.status):
        raise api_error(409, "STORE_NOT_READY", "Dukaan abhi saaman tayyar kar rahi hai.")

    db.add(_history(order.id, StoreOrderStatus.PICKED_UP, from_status=so.status, actor=user, role="DELIVERY_PARTNER", store_order_id=so.id))
    so.status = StoreOrderStatus.PICKED_UP
    if all_stores_picked_up([s.status for s in order.store_orders]):
        delivery.status = DeliveryStatus.PICKED_UP
        db.add(_history(order.id, OrderStatus.PICKED_UP, from_status=order.status, actor=user, role="DELIVERY_PARTNER", note="saari dukaanon se saaman uth gaya"))
        order.status = OrderStatus.PICKED_UP
    await db.commit()
    order = await _load_order(db, order_id, lock=False)
    delivery = await _my_live_delivery(db, delivery.partner_id, order_id)
    return _my_delivery(delivery, order, lang)


async def start_delivery(db: AsyncSession, user: User, order_id: uuid.UUID, lang: str) -> MyDeliveryOut:
    delivery = await _live_for_order(db, user, order_id)
    order: Order = await _load_order(db, order_id, lock=True)
    if delivery.status == DeliveryStatus.OUT_FOR_DELIVERY:  # wahi dobara: kuch nahi badalta
        return _my_delivery(delivery, order, lang)
    if delivery.status != DeliveryStatus.PICKED_UP:
        raise api_error(409, "NOT_ALL_PICKED_UP", "Pehle saari dukaanon se saaman uthao.")

    delivery.status = DeliveryStatus.OUT_FOR_DELIVERY
    db.add(_history(order.id, OrderStatus.OUT_FOR_DELIVERY, from_status=order.status, actor=user, role="DELIVERY_PARTNER"))
    order.status = OrderStatus.OUT_FOR_DELIVERY
    await db.commit()
    order = await _load_order(db, order_id, lock=False)
    delivery = await _my_live_delivery(db, delivery.partner_id, order_id)
    return _my_delivery(delivery, order, lang)


def _delivered_out(delivery: Delivery, order: Order) -> DeliveredOut:
    return DeliveredOut(
        order_id=order.id, order_number=order.order_number, status=OrderStatus.DELIVERED,
        cod_collected=float(delivery.cod_collected or 0), delivered_at=delivery.delivered_at,
    )


def _otp_locked(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429, headers={"Retry-After": str(retry_after)},
        detail={"code": "OTP_LOCKED", "message": "Bahut galat OTP daale gaye. Thodi der baad dobara koshish karo."},
    )


async def complete_delivery(db: AsyncSession, user: User, order_id: uuid.UUID, otp: str) -> DeliveredOut:
    partner = await _partner_for(db, user, lock=True)  # partner row lock: OTP ki koshishein line se chalti hain
    _require_active(partner)

    done = await db.scalar(  # app ne retry kiya (pehla jawab kho gaya): wahi jawab, OTP dobara nahi maangte
        select(Delivery).where(
            Delivery.partner_id == partner.id, Delivery.order_id == order_id, Delivery.status == DeliveryStatus.DELIVERED
        ).execution_options(populate_existing=True)
    )
    if done is not None:
        return _delivered_out(done, await _load_order(db, order_id, lock=False))

    delivery = await _my_live_delivery(db, partner.id, order_id)
    if delivery is None:
        raise api_error(404, "DELIVERY_NOT_FOUND", "Aapke paas ye delivery nahi hai (ya pickup ho chuka hai).")
    if delivery.status != DeliveryStatus.OUT_FOR_DELIVERY:
        raise api_error(409, "INVALID_STATE", "Abhi ki halat me ye kaam nahi ho sakta.")

    now = await db.scalar(select(func.now()))  # database ki ghadi
    if delivery.otp_locked_until is not None and delivery.otp_locked_until > now:
        raise _otp_locked(int((delivery.otp_locked_until - now).total_seconds()) + 1)

    order: Order = await _load_order(db, order_id, lock=True)
    if not otp_matches(settings.jwt_secret, delivery.id, otp):
        delivery.otp_attempts += 1
        locked = delivery.otp_attempts >= OTP_MAX_ATTEMPTS
        if locked:
            delivery.otp_locked_until = now + timedelta(seconds=OTP_LOCK_SECONDS)
            delivery.otp_attempts = 0
        await db.commit()  # galat koshish ginti me judni hi chahiye, isliye error se pehle save
        if locked:
            raise _otp_locked(OTP_LOCK_SECONDS)
        raise api_error(422, "OTP_INVALID", "OTP galat hai.")

    owed = cod_amount_due(order.payment_method, order.payment_status, order.status, order.total)
    delivery.status = DeliveryStatus.DELIVERED
    delivery.delivered_at = now
    delivery.cod_collected = order.total if owed > 0 else Decimal("0.00")
    delivery.otp_attempts = 0
    delivery.otp_locked_until = None
    if owed > 0:  # COD: cash mil gaya
        order.payment_status = PaymentStatus.PAID
    db.add(_history(order.id, OrderStatus.DELIVERED, from_status=order.status, actor=user, role="DELIVERY_PARTNER",
                    note=f"COD cash liya: {order.total}" if owed > 0 else None))
    order.status = OrderStatus.DELIVERED
    await db.commit()
    return _delivered_out(delivery, order)