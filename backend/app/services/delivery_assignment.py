"""Order delivery partner ko milna.

Rules:
- Order customer ke order karte hi (CONFIRMED se) dikhta hai, aur sirf unhi partners ko jo NAZDEEK hain
  (partner se sabse paas wali dukaan NEARBY_RADIUS_KM ke andar). Partner ke area ke SAARE open orders dikhte hain.
- Partner khud accept karta hai (pehle jo accept kare use milta hai). Sirf ACTIVE aur ONLINE partner.
- Ek partner ek samay me kai orders le sakta hai; har order ka pickup / OTP alag rahega.
- Accept ke baad dukaan abhi tayyari me ho to Order ka status nahi badalta; sab tayyar ho tab DELIVERY_ASSIGNED.
- Pickup se pehle partner chhod sakta hai (release). Customer cancel / saari dukaanein reject / partner suspend:
  delivery apne aap free ho jaati hai.
- Customer ka naam/phone/address accept ke baad hi dikhta hai.
Lock ka kram (deadlock se bachne ke liye sab jagah wahi): pehle partner row, phir Order row.
"""
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import localized
from app.models import Delivery, DeliveryPartner, Order, OrderStatusHistory, StoreOrder, User
from app.models.delivery import DeliveryStatus, PartnerStatus
from app.models.order import StoreOrderStatus
from app.schemas.delivery_assignment import AvailableOrderOut, MyDeliveryOut, PickupItemOut, PickupStoreOut
from app.services.cart import km_between
from app.services.delivery_cash import _totals
from app.services.delivery_rules import (
    ACTIVE_DELIVERY_STATUSES,
    MAX_CANDIDATES,
    NEARBY_RADIUS_KM,
    OPEN_ORDER_STATUSES,
    cash_limit_reached,
    cod_amount_due,
    order_status_when_assigned,
    order_status_when_released,
)

INACTIVE_STORE = (StoreOrderStatus.REJECTED, StoreOrderStatus.CANCELLED)


def _history(order_id, to_status, *, from_status, actor: User | None, role: str, note: str | None = None, store_order_id=None):
    return OrderStatusHistory(
        order_id=order_id, store_order_id=store_order_id, from_status=from_status, to_status=to_status,
        actor_id=actor.id if actor else None, actor_role=role, note=note,
    )


# ---------------- order -> card ----------------


def _stores(order: Order, lang: str) -> list[PickupStoreOut]:
    removed = {r.order_item_id for r in order.removals}
    return [
        PickupStoreOut(
            store_order_id=so.id, store_name=so.store_name, store_address=so.store_address,
            latitude=float(so.store_latitude), longitude=float(so.store_longitude), status=so.status,
            items=[
                PickupItemOut(name=localized(i, lang), quantity=i.quantity, selling_unit=i.selling_unit)
                for i in so.items if i.id not in removed
            ],
        )
        for so in order.store_orders if so.status not in INACTIVE_STORE
    ]


def _drop_km(order: Order, stores: list[PickupStoreOut]) -> float:
    lat, lng = float(order.latitude), float(order.longitude)
    return max((km_between(s.latitude, s.longitude, lat, lng) for s in stores), default=0.0)


def _pickup_km(stores: list[PickupStoreOut], lat: float, lng: float) -> float | None:
    """Partner se sabse paas wali dukaan tak doori."""
    return round(min(km_between(lat, lng, s.latitude, s.longitude) for s in stores), 2) if stores else None


def _available_card(order: Order, lat: float, lng: float, lang: str) -> AvailableOrderOut:
    stores = _stores(order, lang)
    return AvailableOrderOut(
        order_id=order.id, order_number=order.order_number, stores=stores, pickup_distance_km=_pickup_km(stores, lat, lng),
        drop_distance_km=round(_drop_km(order, stores), 2), delivery_fee=float(order.delivery_fee),
        payment_method=order.payment_method,
        amount_due=cod_amount_due(order.payment_method, order.payment_status, order.status, order.total),
        created_at=order.created_at,
    )


def _nearby(cards: list[AvailableOrderOut]) -> list[AvailableOrderOut]:
    """Sirf wahi jo partner ke area me hain, paas wale pehle (barabar doori par purana order pehle)."""
    near = [c for c in cards if c.pickup_distance_km is not None and c.pickup_distance_km <= NEARBY_RADIUS_KM]
    return sorted(near, key=lambda c: (c.pickup_distance_km, c.created_at))


def _my_delivery(delivery: Delivery, order: Order, lang: str) -> MyDeliveryOut:
    return MyDeliveryOut(
        delivery_id=delivery.id, order_id=order.id, order_number=order.order_number, status=delivery.status,
        order_status=order.status, assigned_at=delivery.assigned_at, stores=_stores(order, lang),
        receiver_name=order.receiver_name, receiver_phone=order.receiver_phone, address_line=order.address_line,
        landmark=order.landmark, latitude=float(order.latitude), longitude=float(order.longitude),
        delivery_fee=float(order.delivery_fee), payment_method=order.payment_method,
        amount_due=cod_amount_due(order.payment_method, order.payment_status, order.status, order.total),
    )


# ---------------- partner ----------------


async def _partner_for(db: AsyncSession, user: User, *, lock: bool) -> DeliveryPartner:
    q = select(DeliveryPartner).where(DeliveryPartner.user_id == user.id).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    partner = await db.scalar(q)
    if partner is None:
        raise api_error(403, "NOT_A_PARTNER", "Pehle delivery partner ke liye apply karo.")
    return partner


def _require_working(partner: DeliveryPartner) -> None:
    if partner.status != PartnerStatus.ACTIVE:
        raise api_error(403, "PARTNER_NOT_ACTIVE", "Aapka delivery partner account abhi active nahi hai.")
    if not partner.is_online:
        raise api_error(409, "PARTNER_OFFLINE", "Pehle online ho jaiye.")


async def _my_live_delivery(db: AsyncSession, partner_id: uuid.UUID, order_id: uuid.UUID | None = None) -> Delivery | None:
    q = select(Delivery).where(Delivery.partner_id == partner_id, Delivery.status.in_(ACTIVE_DELIVERY_STATUSES))
    if order_id is not None:
        q = q.where(Delivery.order_id == order_id)
    return await db.scalar(q.execution_options(populate_existing=True))


async def _load_order(db: AsyncSession, order_id: uuid.UUID, *, lock: bool) -> Order | None:
    q = select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    return await db.scalar(q)
async def _require_under_cash_limit(db: AsyncSession, partner: DeliveryPartner) -> None:
    """Admin ki lagayi cash limit: partner ke paas utna COD cash ho gaya to jama karne tak naya order nahi."""
    collected, deposited = await _totals(db, partner.id)
    if cash_limit_reached(collected - deposited, partner.cash_limit):
        raise api_error(409, "CASH_LIMIT_REACHED", "Aapke paas cash limit tak pahunch gaya hai. Pehle cash jama karo.")


# ---------------- actions ----------------


async def list_available(
    db: AsyncSession, user: User, lat: float, lng: float, limit: int, offset: int, lang: str
) -> list[AvailableOrderOut]:
    """Partner ke area ke saare open orders (customer ke order karte hi se), paas wale pehle."""
    partner = await _partner_for(db, user, lock=False)
    _require_working(partner)
    await _require_under_cash_limit(db, partner)
    # Pehle database me chhota dabba (bounding box) se chhaanto, phir sahi doori python me
    dlat = NEARBY_RADIUS_KM / 111.0
    dlng = NEARBY_RADIUS_KM / (111.0 * max(0.1, math.cos(math.radians(lat))))
    d = lambda x: Decimal(str(round(x, 6)))  # noqa: E731
    near_orders = select(StoreOrder.order_id).where(
        StoreOrder.status.not_in(INACTIVE_STORE),
        StoreOrder.store_latitude.between(d(lat - dlat), d(lat + dlat)),
        StoreOrder.store_longitude.between(d(lng - dlng), d(lng + dlng)),
    )
    live = select(Delivery.order_id).where(Delivery.status != DeliveryStatus.RELEASED)
    q = (
        select(Order)
        .where(Order.status.in_(OPEN_ORDER_STATUSES), Order.id.in_(near_orders), Order.id.not_in(live))
        .order_by(Order.created_at, Order.id)
        .limit(MAX_CANDIDATES)
        .execution_options(populate_existing=True)
    )
    cards = _nearby([_available_card(o, lat, lng, lang) for o in await db.scalars(q)])
    return cards[offset: offset + limit]


async def accept(db: AsyncSession, user: User, order_id: uuid.UUID, lat: float, lng: float, lang: str) -> MyDeliveryOut:
    partner = await _partner_for(db, user, lock=True)  # partner row lock: uske do accept ek saath line se chalte hain
    _require_working(partner)

    mine = await _my_live_delivery(db, partner.id, order_id)
    if mine is not None:  # wahi order dobara accept: kuch nahi badalta (app retry safe)
        order = await _load_order(db, order_id, lock=False)
        return _my_delivery(mine, order, lang)
    await _require_under_cash_limit(db, partner)

    order = await _load_order(db, order_id, lock=True)  # seller / customer cancel ke saath line me
    if order is None:
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")
    taken = await db.scalar(
        select(Delivery.id).where(Delivery.order_id == order.id, Delivery.status != DeliveryStatus.RELEASED)
    )
    if order.status not in OPEN_ORDER_STATUSES or taken is not None:
        raise api_error(409, "ORDER_NOT_AVAILABLE", "Ye order ab available nahi hai.")
    km = _pickup_km(_stores(order, lang), lat, lng)
    if km is None or km > NEARBY_RADIUS_KM:  # list me na dikhne wala order id se bhi accept nahi hoga
        raise api_error(409, "ORDER_TOO_FAR", "Ye order aapke area se bahar hai.")

    new_status = order_status_when_assigned(order.status)
    delivery = Delivery(order_id=order.id, partner_id=partner.id, status=DeliveryStatus.ASSIGNED)
    db.add(delivery)
    db.add(_history(order.id, new_status, from_status=order.status, actor=user, role="DELIVERY_PARTNER", note="delivery partner ne accept kiya"))
    order.status = new_status
    try:
        await db.commit()
    except IntegrityError:  # database ne rok diya (order kisi aur partner ne pehle le liya)
        await db.rollback()
        raise api_error(409, "ORDER_NOT_AVAILABLE", "Ye order ab available nahi hai.")
    order = await _load_order(db, order_id, lock=False)
    delivery = await _my_live_delivery(db, partner.id, order_id)
    return _my_delivery(delivery, order, lang)


def _release(db: AsyncSession, delivery: Delivery, order: Order, *, actor: User, role: str, reason: str) -> None:
    delivery.status = DeliveryStatus.RELEASED
    delivery.released_at = datetime.now(timezone.utc)
    delivery.release_reason = reason
    new_status = order_status_when_released(order.status)
    db.add(_history(order.id, new_status, from_status=order.status, actor=actor, role=role, note=reason))
    order.status = new_status


async def release(db: AsyncSession, user: User, order_id: uuid.UUID) -> uuid.UUID:
    """Pickup se pehle order chhodna. Order wapas nazdeek ke partners ko dikhne lagta hai."""
    partner = await _partner_for(db, user, lock=True)
    delivery = await db.scalar(
        select(Delivery).where(Delivery.partner_id == partner.id, Delivery.order_id == order_id, Delivery.status == DeliveryStatus.ASSIGNED)
        .execution_options(populate_existing=True)
    )
    if delivery is None:
        raise api_error(404, "DELIVERY_NOT_FOUND", "Aapke paas ye delivery nahi hai (ya pickup ho chuka hai).")
    order = await _load_order(db, order_id, lock=True)
    if order.status == "CANCELLED":  # isi beech customer ne cancel kar diya (delivery wahan free ho chuki)
        raise api_error(404, "DELIVERY_NOT_FOUND", "Aapke paas ye delivery nahi hai (ya pickup ho chuka hai).")
    if any(s.status == StoreOrderStatus.PICKED_UP for s in order.store_orders):  # kisi dukaan se saaman uth chuka
        raise api_error(409, "ALREADY_PICKED_UP", "Saaman uth chuka hai, ab order chhod nahi sakte.")
    _release(db, delivery, order, actor=user, role="DELIVERY_PARTNER", reason="partner ne order chhoda")
    await db.commit()
    return order_id


async def release_assigned(db: AsyncSession, partner_id: uuid.UUID, admin: User) -> int:
    """Partner suspend hua: pickup se pehle wale orders wapas free. Caller commit karta hai (partner row pehle se lock).
    Jis partner ke paas customer ka saaman hai (kisi dukaan se uth chuka) use suspend nahi kar sakte: 409 PARTNER_HAS_GOODS."""
    if await db.scalar(
        select(Delivery.id).where(Delivery.partner_id == partner_id, Delivery.status.in_((DeliveryStatus.PICKED_UP, DeliveryStatus.OUT_FOR_DELIVERY)))
    ) is not None:
        raise api_error(409, "PARTNER_HAS_GOODS", "Partner ke paas abhi customer ka saaman hai, pehle delivery poori hone do.")
    deliveries = list(
        await db.scalars(
            select(Delivery).where(Delivery.partner_id == partner_id, Delivery.status == DeliveryStatus.ASSIGNED)
            .execution_options(populate_existing=True)
        )
    )
    for d in sorted(deliveries, key=lambda x: str(x.order_id)):
        order = await _load_order(db, d.order_id, lock=True)
        if order.status == "CANCELLED":  # order cancel ho chuka, delivery pehle hi free
            continue
        if any(s.status == StoreOrderStatus.PICKED_UP for s in order.store_orders):  # ek dukaan se saaman uth chuka
            raise api_error(409, "PARTNER_HAS_GOODS", "Partner ke paas abhi customer ka saaman hai, pehle delivery poori hone do.")
        _release(db, d, order, actor=admin, role="SUPER_ADMIN", reason="partner suspend hua")
    return len(deliveries)

async def has_live_delivery(db: AsyncSession, partner_id: uuid.UUID) -> bool:
    return await _my_live_delivery(db, partner_id) is not None


async def cancel_live_delivery(db: AsyncSession, order_id: uuid.UUID, reason: str) -> None:
    """Order cancel ho gaya (customer ne ya saari dukaanein reject): partner ko free karo. Caller Order row lock kar chuka hai
    aur commit karta hai. Order ka status yahan nahi chhedte (wo caller ne CANCELLED kar diya hai)."""
    delivery = await db.scalar(
        select(Delivery).where(Delivery.order_id == order_id, Delivery.status.in_(ACTIVE_DELIVERY_STATUSES))
        .with_for_update().execution_options(populate_existing=True)
    )
    if delivery is not None:
        delivery.status = DeliveryStatus.RELEASED
        delivery.released_at = datetime.now(timezone.utc)
        delivery.release_reason = reason


async def current(db: AsyncSession, user: User, lang: str) -> list[MyDeliveryOut]:
    partner = await _partner_for(db, user, lock=False)
    deliveries = await db.scalars(
        select(Delivery).where(Delivery.partner_id == partner.id, Delivery.status.in_(ACTIVE_DELIVERY_STATUSES))
        .order_by(Delivery.assigned_at, Delivery.id).execution_options(populate_existing=True)
    )
    result = []
    for delivery in deliveries:
        order = await _load_order(db, delivery.order_id, lock=False)
        if order is not None:
            result.append(_my_delivery(delivery, order, lang))
    return result
