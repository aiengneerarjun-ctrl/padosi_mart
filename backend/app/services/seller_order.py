"""Seller ka order handling: apni dukaan ke StoreOrder ko accept / preparing / ready karna, aur jo saaman nahi hai use hatana.

Rules:
- Seller sirf apne StoreOrder dekh/badal sakta hai (doosre ka = 404). Suspended seller sirf dekh sakta hai.
- Status ka kram: PLACED -> SELLER_ACCEPTED -> PREPARING -> READY_FOR_PICKUP (SELLER_ACCEPTED se seedha READY bhi chalega).
- Wahi action dobara bhejna error nahi (jaisa hai waisa hi wapas).
- "Saaman nahi hai" (item-level): seller kuch items hata sakta hai, baaki order chalta rehta hai (PLACED / SELLER_ACCEPTED / PREPARING me).
  Hatane ka record order_item_removals me judta hai, customer ko karan + naya total dikhta hai.
  * hataye item ka stock wapas aata hai; karan OUT_OF_STOCK ho to us product ka bacha hua stock bhi 0 kar diya jaata hai
    (warna system doosre customers ko wahi saaman bechta rahega).
  * order ka total = bache hue items + delivery charge (delivery charge waisa hi rehta hai).
  * dukaan ke saare items hat gaye = us dukaan ka hissa REJECTED. Saari dukaanein REJECTED/CANCELLED = poora order CANCELLED.
- Poore Order ka status = sabse peeche wali (kam aage badhi) dukaan ka status.
- Customer ke cancel se takrao na ho, isliye pehle Order row lock hoti hai (customer cancel bhi yahi karta hai).
"""
import uuid
from decimal import Decimal
from math import ceil

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import localized, translate
from app.models import Delivery, Order, OrderStatusHistory, Seller, StoreOrder, User
from app.models.catalog import StockReason
from app.models.order import OrderItemRemoval, OrderStatus, PaymentStatus, RemovalReason, StoreOrderStatus
from app.models.seller import SellerStatus
from app.schemas.seller_order import SellerOrderItem, SellerOrderOut, UnavailableItem
from app.services.checkout import delivery_fee_for
from app.services.delivery_assignment import cancel_live_delivery
from app.services.inventory import adjust_stock

S = StoreOrderStatus
# kis status se kahan jaa sakte hain
TRANSITIONS: dict[str, tuple[str, ...]] = {
    S.PLACED: (S.SELLER_ACCEPTED, S.REJECTED),
    S.SELLER_ACCEPTED: (S.PREPARING, S.READY_FOR_PICKUP),
    S.PREPARING: (S.READY_FOR_PICKUP,),
    S.READY_FOR_PICKUP: (),
}
# Item sirf accept se pehle hat sakta hai (accept ke baad customer cancel nahi kar sakta, isliye hatana bhi band)
CAN_REMOVE_ITEMS_IN = (S.PLACED,)
# Item hatane ke baad itne second tak seller accept nahi kar sakta (customer ko cancel ka mauka)
ACCEPT_WAIT_SECONDS = 120
ROLLUP_RANK = {S.SELLER_ACCEPTED: 1, S.PREPARING: 2, S.READY_FOR_PICKUP: 3, S.PICKED_UP: 3}  # PICKED_UP = tayyar se aage, par order ko READY hi ginte hain
ROLLUP_ORDER_STATUS = {1: OrderStatus.SELLER_ACCEPTED, 2: OrderStatus.PREPARING, 3: OrderStatus.READY_FOR_PICKUP}
INACTIVE = (S.REJECTED, S.CANCELLED)


def can_move(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, ())


def rollup_status(store_statuses: list[str]) -> str | None:
    """Dukaanon ke status se Order ka status. None = abhi koi badlav nahi (kisi dukaan ne accept hi nahi kiya)."""
    active = [s for s in store_statuses if s not in INACTIVE]
    if not active or any(s == S.PLACED for s in active):
        return None
    ranks = [ROLLUP_RANK.get(s) for s in active]
    if None in ranks:  # PICKED_UP jaise status: delivery wale step me
        return None
    return ROLLUP_ORDER_STATUS[min(ranks)]


def _require_active(seller: Seller) -> None:
    if seller.status != SellerStatus.ACTIVE:
        raise api_error(403, "SELLER_NOT_ACTIVE", "Aapka seller account abhi active nahi hai.")


def _history(order_id, to_status, *, store_order_id=None, from_status=None, actor: User | None, role: str, note=None):
    return OrderStatusHistory(
        order_id=order_id, store_order_id=store_order_id, from_status=from_status, to_status=to_status,
        actor_id=actor.id if actor else None, actor_role=role, note=note[:300] if note else None,
    )


def _out(so: StoreOrder, order: Order, lang: str) -> SellerOrderOut:
    removal_of = {r.order_item_id: r for r in order.removals}
    return SellerOrderOut(
        id=so.id, order_id=order.id, order_number=order.order_number, store_id=so.store_id, store_name=so.store_name,
        status=so.status, payment_method=order.payment_method, items_subtotal=float(so.items_subtotal),
        items=[
            SellerOrderItem(
                id=i.id, product_id=i.product_id, name=localized(i, lang), selling_unit=i.selling_unit, quantity=i.quantity,
                unit_price=float(i.unit_price), line_total=float(i.line_total), removed=i.id in removal_of,
                removed_reason_code=removal_of[i.id].reason_code if i.id in removal_of else None,
                removed_reason=translate(f"REMOVAL_REASON_{removal_of[i.id].reason_code}", lang) if i.id in removal_of else None,
            )
            for i in so.items
        ],
        created_at=so.created_at, updated_at=so.updated_at,
    )


# ---------------- Read ----------------


async def list_orders(db: AsyncSession, seller: Seller, status: str | None, limit: int, offset: int, lang: str) -> list[SellerOrderOut]:
    q = (
        select(StoreOrder, Order)
        .join(Order, Order.id == StoreOrder.order_id)
        .where(StoreOrder.seller_id == seller.id)
        .order_by(StoreOrder.created_at.desc(), StoreOrder.id)
        .limit(limit)
        .offset(offset)
    )
    if status:
        q = q.where(StoreOrder.status == status)
    return [_out(so, o, lang) for so, o in (await db.execute(q)).all()]


async def get_order(db: AsyncSession, seller: Seller, store_order_id: uuid.UUID, lang: str) -> SellerOrderOut:
    row = (
        await db.execute(
            select(StoreOrder, Order).join(Order, Order.id == StoreOrder.order_id)
            .where(StoreOrder.id == store_order_id, StoreOrder.seller_id == seller.id)
        )
    ).first()
    if row is None:  # doosre seller ka bhi 404
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")
    return _out(row[0], row[1], lang)


# ---------------- Actions ----------------


async def _lock(db: AsyncSession, seller: Seller, store_order_id: uuid.UUID) -> tuple[Order, StoreOrder]:
    """Pehle Order row lock (customer cancel ke saath line me), phir taaza StoreOrder/items/removals."""
    order_id = await db.scalar(
        select(StoreOrder.order_id).where(StoreOrder.id == store_order_id, StoreOrder.seller_id == seller.id)
    )
    if order_id is None:
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True))
    so = next(s for s in order.store_orders if s.id == store_order_id)
    return order, so


async def _reload(db: AsyncSession, order_id: uuid.UUID, store_order_id: uuid.UUID) -> tuple[Order, StoreOrder]:
    """Commit ke baad taaza data (updated_at, naye removals ke saath)."""
    order = await db.scalar(select(Order).where(Order.id == order_id).execution_options(populate_existing=True))
    return order, next(s for s in order.store_orders if s.id == store_order_id)


def _apply_rollup(db: AsyncSession, order: Order, assigned: bool = False) -> None:
    target = rollup_status([s.status for s in order.store_orders])
    if target == OrderStatus.READY_FOR_PICKUP and assigned:  # partner pehle hi accept kar chuka hai
        target = OrderStatus.DELIVERY_ASSIGNED
async def _accept_wait_left(db: AsyncSession, order: Order, so: StoreOrder) -> int:
    """Item hatane ke baad accept se pehle kitne second aur ruke (0 = ruka nahi). Samay database ki ghadi se."""
    last = max((r.created_at for r in order.removals if r.store_order_id == so.id), default=None)
    if last is None:
        return 0
    now = await db.scalar(select(func.clock_timestamp()))
    return max(0, ceil(ACCEPT_WAIT_SECONDS - (now - last).total_seconds()))

async def move(db: AsyncSession, seller: Seller, user: User, store_order_id: uuid.UUID, target: str, lang: str) -> SellerOrderOut:
    _require_active(seller)
    order, so = await _lock(db, seller, store_order_id)
    if so.status == target:  # wahi action dobara: kuch nahi badalta
        return _out(so, order, lang)
    if order.status == OrderStatus.CANCELLED or not can_move(so.status, target):
        raise api_error(409, "INVALID_STATE", "Abhi ki halat me ye kaam nahi ho sakta.")
    if target == S.SELLER_ACCEPTED:
        wait = await _accept_wait_left(db, order, so)
        if wait > 0:  # customer ko naya total dekhkar cancel karne ka time dena hai
            raise HTTPException(
                status_code=409, headers={"Retry-After": str(wait)},
                detail={"code": "ACCEPT_WAIT", "message": "Aapne items hataye hain. Customer ko cancel ka mauka dene ke liye 2 minute baad accept karein."},
            )

    db.add(_history(order.id, target, store_order_id=so.id, from_status=so.status, actor=user, role="SELLER"))
    so.status = target
    _apply_rollup(db, order)
    await db.commit()
    order, so = await _reload(db, order.id, so.id)
    return _out(so, order, lang)


async def _remove_items(
    db: AsyncSession, order: Order, so: StoreOrder, user: User, picks: dict[uuid.UUID, tuple[str, str | None]]
) -> int:
    """picks = {order_item_id: (reason_code, note)}. Naye hataye gaye items ki ginti lautata hai (pehle se hate hue chhod deta hai)."""
    already = {r.order_item_id for r in order.removals}
    new = [i for i in so.items if i.id in picks and i.id not in already]
    if not new:
        return 0

    # Stock: hataye item ka stock wapas; OUT_OF_STOCK ho to bacha hua bhi 0 (product_id ke order me, deadlock se bachne ke liye)
    per_product: dict[uuid.UUID, tuple[int, bool]] = {}
    for i in new:
        qty, zero = per_product.get(i.product_id, (0, False))
        per_product[i.product_id] = (qty + i.quantity, zero or picks[i.id][0] == RemovalReason.OUT_OF_STOCK)
    for pid in sorted(per_product):
        qty, zero = per_product[pid]
        left = await adjust_stock(db, pid, qty, StockReason.ORDER_CANCEL, actor=user, note=f"order {order.order_no}: seller ne item hataya")
        if zero and left > 0:
            await adjust_stock(db, pid, -left, StockReason.ADJUSTMENT, actor=user, note=f"order {order.order_no}: seller ne kaha saaman nahi hai")

    for i in new:
        code, note = picks[i.id]
        db.add(
            OrderItemRemoval(
                order_id=order.id, store_order_id=so.id, order_item_id=i.id, reason_code=code, note=note,
                line_total=i.line_total, actor_id=user.id,
            )
        )
    removed_ids = already | {i.id for i in new}

    # Is dukaan ka naya hisaab
    so.items_subtotal = sum((i.line_total for i in so.items if i.id not in removed_ids), Decimal("0"))
    removed_amount = sum((i.line_total for i in new), Decimal("0"))
    if all(i.id in removed_ids for i in so.items):  # dukaan ke saare items hat gaye = poora hissa REJECTED
        db.add(_history(order.id, S.REJECTED, store_order_id=so.id, from_status=so.status, actor=user, role="SELLER", note="saare items available nahi"))
        so.status = S.REJECTED
    else:
        db.add(_history(order.id, so.status, store_order_id=so.id, from_status=so.status, actor=user, role="SELLER", note=f"{len(new)} item hataye (rs {removed_amount})"))

    # Poore order ka naya hisaab
    live = [s for s in order.store_orders if s.status not in INACTIVE]
    if not live:  # koi dukaan nahi bachi
        db.add(_history(order.id, OrderStatus.CANCELLED, from_status=order.status, actor=None, role="SYSTEM", note="saare items available nahi"))
        order.status = OrderStatus.CANCELLED
        if order.payment_status == PaymentStatus.PENDING:
            order.payment_status = PaymentStatus.NOT_REQUIRED
        await cancel_live_delivery(db, order.id, "saari dukaanein reject / items nahi")  # partner ko free karo
    else:
        old_total, old_fee = order.total, order.delivery_fee
        order.items_subtotal = sum((s.items_subtotal for s in live), Decimal("0"))
        order.delivery_fee = max(old_fee, delivery_fee_for(order.items_subtotal))  # 799 se neeche aaye to charge lagega
        order.total = order.items_subtotal + order.delivery_fee
        fee_note = f", delivery {old_fee} -> {order.delivery_fee}" if order.delivery_fee != old_fee else ""
        db.add(_history(order.id, order.status, from_status=order.status, actor=None, role="SYSTEM", note=f"{so.store_name}: total {old_total} -> {order.total}{fee_note}"))
        _apply_rollup(db, order)
    return len(new)

def _clean_picks(items: list[UnavailableItem], valid_ids: set[uuid.UUID]) -> dict[uuid.UUID, tuple[str, str | None]]:
    picks: dict[uuid.UUID, tuple[str, str | None]] = {}
    for it in items:
        if it.item_id not in valid_ids:
            raise api_error(404, "ORDER_ITEM_NOT_FOUND", "Ye saaman is order me nahi hai.")
        note = (it.note or "").strip() or None
        if it.reason == RemovalReason.OTHER and (note is None or len(note) < 3):
            raise api_error(422, "REMOVAL_NOTE_REQUIRED", "'Other' chunne par karan likhna zaroori hai.")
        picks[it.item_id] = (it.reason, note)
    return picks


async def mark_unavailable(
    db: AsyncSession, seller: Seller, user: User, store_order_id: uuid.UUID, items: list[UnavailableItem], lang: str
) -> SellerOrderOut:
    """Kuch items dukaan me nahi hain: unhe hatao, baaki order chalta rahega."""
    _require_active(seller)
    order, so = await _lock(db, seller, store_order_id)
    picks = _clean_picks(items, {i.id for i in so.items})
    if all(i in {r.order_item_id for r in order.removals} for i in picks):  # sab pehle hi hat chuke: kuch nahi badalta
        return _out(so, order, lang)
    if order.status == OrderStatus.CANCELLED or so.status not in CAN_REMOVE_ITEMS_IN:
        raise api_error(409, "INVALID_STATE", "Abhi ki halat me ye kaam nahi ho sakta.")
    await _remove_items(db, order, so, user, picks)
    await db.commit()
    order, so = await _reload(db, order.id, so.id)
    return _out(so, order, lang)


async def reject(
    db: AsyncSession, seller: Seller, user: User, store_order_id: uuid.UUID, reason: str, reason_code: str, lang: str
) -> SellerOrderOut:
    """Poori dukaan ka hissa lene se mana (sirf PLACED me). Saare items hat jaate hain, karan customer ko dikhta hai."""
    _require_active(seller)
    order, so = await _lock(db, seller, store_order_id)
    if so.status == S.REJECTED:
        return _out(so, order, lang)
    if order.status == OrderStatus.CANCELLED or not can_move(so.status, S.REJECTED):
        raise api_error(409, "INVALID_STATE", "Abhi ki halat me ye kaam nahi ho sakta.")
    note = reason.strip()
    await _remove_items(db, order, so, user, {i.id: (reason_code, note) for i in so.items})
    await db.commit()
    order, so = await _reload(db, order.id, so.id)
    return _out(so, order, lang)