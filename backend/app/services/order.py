"""Orders: banana (place), dekhna, cancel karna.

Rules:
- Ek checkout = ek Order; har dukaan ka alag StoreOrder (seller ka paisa aur delivery pickup usi se).
- Idempotency-Key: wahi key dobara aaye to naya order nahi banta, purana hi wapas milta hai.
- Customer ka dekha hua total (expected_total) badal gaya to order nahi banta.
- Stock sirf inventory.adjust_stock() se kat'ta hai (atomic). Koi bhi gadbad ho to poora order rollback.
- Paisa hamesha Decimal.
"""
import uuid
from decimal import Decimal
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.errors import api_error
from app.core.i18n import localized, translate, translate_fmt
from app.models import Delivery, Order, OrderItem, OrderStatusHistory, Product, Seller, Store, StoreOrder, User
from app.models.cart import Cart, CartItem
from app.models.catalog import StockReason
from app.models.order import OrderStatus, PaymentMethod, PaymentStatus, StoreOrderStatus
from app.schemas.order import (
    AddressSnapshotOut, OrderCreate, OrderItemOut, OrderOut, OrderSummary, RemovedItemOut, StatusHistoryOut, StoreOrderOut,
)
from app.services import checkout as checkout_service
from app.services import customer as customer_service
from app.services import notification
from app.services.delivery_assignment import cancel_live_delivery
from app.services.delivery_rules import delivery_otp
from app.services.inventory import adjust_stock
from app.services.seller_order import ACCEPT_WAIT_SECONDS

CENT = Decimal("0.01")
CANCELLABLE_ORDER_STATUSES = (OrderStatus.PLACED, OrderStatus.CONFIRMED)


async def _lock_user(db: AsyncSession, user: User) -> None:
    # Ek customer ke do request ek saath aayein to line se chalein (double order / double cancel na ho)
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
def _can_cancel(order: Order) -> bool:
    """Customer tab tak cancel kar sakta hai jab tak koi bhi (reject na hui) dukaan accept na kar le."""
    live = [so for so in order.store_orders if so.status != StoreOrderStatus.REJECTED]
    return order.status in CANCELLABLE_ORDER_STATUSES and all(so.status == StoreOrderStatus.PLACED for so in live)

def _history(order_id, to_status, actor: User | None, role, *, store_order_id=None, from_status=None, note=None):
    return OrderStatusHistory(
        order_id=order_id, store_order_id=store_order_id, from_status=from_status, to_status=to_status,
        actor_id=actor.id if actor else None, actor_role=role, note=note,
    )


# ---------------- Place ----------------


async def place_order(db: AsyncSession, user: User, body: OrderCreate, idempotency_key: str, lang: str) -> tuple[OrderOut, bool]:
    """(order, naya_bana) lautata hai. naya_bana False = ye wahi purana order hai (idempotent replay)."""
    await _lock_user(db, user)

    existing = await db.scalar(select(Order).where(Order.user_id == user.id, Order.idempotency_key == idempotency_key))
    if existing is not None:
        return await _order_out(db, existing, lang), False

    if body.payment_method != PaymentMethod.COD:
        raise api_error(409, "PAYMENT_METHOD_NOT_AVAILABLE", "Ye payment tareeka abhi available nahi hai.")

    # Address, doori, delivery radius, dukaan OPEN, stock: sab preview wale hi rules se dobara check
    preview = await checkout_service.preview(db, user, body.address_id, lang)
    if "CART_EMPTY" in preview.blockers:
        raise api_error(409, "CART_EMPTY", "Aapka cart khali hai.")
    if not preview.can_checkout:
        raise api_error(409, "CART_HAS_UNAVAILABLE_ITEMS", "Cart ke kuch items abhi available nahi hain. Unhe hata dijiye.")
    address = await customer_service._get_own(db, user, body.address_id) if body.address_id else (
        await customer_service.list_addresses(db, user)
    )[0]

    # Quantity cart se, price/naam products table se (Decimal)
    wanted = {i.product_id: i.quantity for g in preview.stores for i in g.items}
    products = {p.id: p for p in (await db.scalars(select(Product).where(Product.id.in_(wanted)))).all()}
    stores = {s.id: s for s in (await db.scalars(select(Store).where(Store.id.in_({p.store_id for p in products.values()})))).all()}

    by_store: dict[uuid.UUID, list[tuple[Product, int]]] = {}
    for pid, qty in wanted.items():
        by_store.setdefault(products[pid].store_id, []).append((products[pid], qty))

    items_subtotal = sum((p.selling_price * q for lines in by_store.values() for p, q in lines), Decimal("0")).quantize(CENT)
    fee = checkout_service.delivery_fee_for(items_subtotal)
    total = (items_subtotal + fee).quantize(CENT)
    if body.expected_total.quantize(CENT) != total:
        raise api_error(409, "PRICE_CHANGED", "Total badal gaya hai. Cart dobara dekhkar order karein.")

    order = Order(
        user_id=user.id, idempotency_key=idempotency_key, status=OrderStatus.PLACED, payment_method=body.payment_method,
        payment_status=PaymentStatus.PENDING,
        receiver_name=address.receiver_name, receiver_phone=address.receiver_phone, address_line=address.address_line,
        landmark=address.landmark, latitude=address.latitude, longitude=address.longitude,
        items_subtotal=items_subtotal, delivery_fee=fee, total=total, note=(body.note or "").strip() or None,
        original_items_subtotal=items_subtotal, original_total=total,
    )
    db.add(order)
    await db.flush()
    db.add(_history(order.id, OrderStatus.PLACED, user, "CUSTOMER"))

    # Dukaan ke hisaab se StoreOrder + lines
    for store_id, lines in by_store.items():
        store = stores[store_id]
        so = StoreOrder(
            order_id=order.id, store_id=store.id, seller_id=store.seller_id, status=StoreOrderStatus.PLACED,
            store_name=store.name, store_address=store.address, store_latitude=store.latitude, store_longitude=store.longitude,
            items_subtotal=sum((p.selling_price * q for p, q in lines), Decimal("0")).quantize(CENT),
        )
        db.add(so)
        await db.flush()
        for p, q in lines:
            db.add(
                OrderItem(
                    order_id=order.id, store_order_id=so.id, product_id=p.id, name=p.name, name_hi=p.name_hi,
                    name_bho=p.name_bho, selling_unit=p.selling_unit, mrp=p.mrp, unit_price=p.selling_price, quantity=q,
                    line_total=(p.selling_price * q).quantize(CENT),
                )
            )
        db.add(_history(order.id, StoreOrderStatus.PLACED, user, "CUSTOMER", store_order_id=so.id))

    # Stock: product_id ke order me (deadlock se bachne ke liye), har ek atomic
    try:
        for pid in sorted(wanted):
            await adjust_stock(db, pid, -wanted[pid], StockReason.ORDER, actor=user, note=f"order {order.order_no}")
    except Exception as e:
        detail = getattr(e, "detail", None)
        if isinstance(detail, dict) and detail.get("code") == "NOT_ENOUGH_STOCK":  # kisi aur ne aakhri piece le liya
            raise api_error(409, "ORDER_ITEMS_CHANGED", "Kuch items ka stock ab kam hai. Cart dobara dekhein.")
        raise

    # COD me online payment ka intezaar nahi: order seedha CONFIRMED
    if order.payment_method == PaymentMethod.COD:
        order.status = OrderStatus.CONFIRMED
        db.add(_history(order.id, OrderStatus.CONFIRMED, None, "SYSTEM", from_status=OrderStatus.PLACED, note="COD"))
        # NAYA: har dukaan ke seller ko "naya order" (usi transaction me)
        seller_user = dict((await db.execute(select(Seller.id, Seller.user_id).where(Seller.id.in_({s.seller_id for s in stores.values()})))).all())
        for store in stores.values():
            notification.add(db, seller_user[store.seller_id], "SELLER_NEW_ORDER", {"order_no": f"PD{order.order_no}", "store_name": store.name}, order.id)

    # Cart khali
    cart_id = await db.scalar(select(Cart.id).where(Cart.user_id == user.id))
    if cart_id:
        await db.execute(CartItem.__table__.delete().where(CartItem.cart_id == cart_id))

    await db.commit()
    return await _order_out(db, order, lang), True

# ---------------- Read ----------------


def _removal_label(code: str, lang: str) -> str:
    return translate(f"REMOVAL_REASON_{code}", lang)


async def _order_out(db: AsyncSession, order: Order, lang: str) -> OrderOut:
    # Taaza data DB se dobara (naye bane store_orders/items/removals bhi saath aayein)
    order = await db.scalar(select(Order).where(Order.id == order.id).execution_options(populate_existing=True))
    history = (
        await db.scalars(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id).order_by(OrderStatusHistory.seq)
        )
    ).all()
    removal_of = {r.order_item_id: r for r in order.removals}

    def item_out(i: OrderItem) -> OrderItemOut:
        r = removal_of.get(i.id)
        return OrderItemOut(
            product_id=i.product_id, name=localized(i, lang), selling_unit=i.selling_unit, mrp=float(i.mrp),
            unit_price=float(i.unit_price), quantity=i.quantity, line_total=float(i.line_total),
            removed=r is not None, removed_reason_code=r.reason_code if r else None,
            removed_reason=_removal_label(r.reason_code, lang) if r else None, removed_note=r.note if r else None,
            removed_kept_quantity=r.kept_quantity if r else None,
        )

    stores = [
        StoreOrderOut(
            id=so.id, store_id=so.store_id, store_name=so.store_name, store_address=so.store_address, status=so.status,
            items_subtotal=float(so.items_subtotal), items=[item_out(i) for i in so.items],
        )
        for so in order.store_orders
    ]
    removed_items = [
           RemovedItemOut(
            product_id=i.product_id, name=localized(i, lang), selling_unit=i.selling_unit,
            quantity=i.quantity - (removal_of[i.id].kept_quantity or 0),  # aadha saaman me sirf jo nahi mila
            line_total=float(removal_of[i.id].line_total), store_name=so.store_name, reason_code=removal_of[i.id].reason_code,
            reason=_removal_label(removal_of[i.id].reason_code, lang), note=removal_of[i.id].note,
            kept_quantity=removal_of[i.id].kept_quantity,
        )
        for so in order.store_orders for i in so.items if i.id in removal_of
    ]
    removed_total = sum((r.line_total for r in order.removals), Decimal("0"))
    all_removed = bool(removal_of) and all(i.id in removal_of for so in order.store_orders for i in so.items)
    can_cancel = _can_cancel(order)
    fee_added = max(Decimal("0"), order.delivery_fee - (order.original_total - order.original_items_subtotal))
    notice = None
    if all_removed:
        notice = translate("ORDER_NOTICE_ALL_REMOVED", lang)
    elif removal_of and order.status != OrderStatus.CANCELLED:  # customer ne khud cancel kiya ho to ye sandesh nahi
        if fee_added > 0:
            notice = translate_fmt(
                "ORDER_NOTICE_ITEMS_REMOVED_FEE", lang, count=len(removal_of), total=f"{order.total:.2f}",
                fee=f"{fee_added:.2f}", free_from=f"{checkout_service.FREE_DELIVERY_FROM:.0f}",
            )
        else:
            notice = translate_fmt("ORDER_NOTICE_ITEMS_REMOVED", lang, count=len(removal_of), total=f"{order.total:.2f}")
        if can_cancel:  # customer ko saaf batao ki wo cancel kar sakta hai
            notice += " " + translate("ORDER_NOTICE_CAN_CANCEL", lang)
    waits = [
        max(r.created_at for r in order.removals if r.store_order_id == so.id) + timedelta(seconds=ACCEPT_WAIT_SECONDS)
        for so in order.store_orders if so.status == StoreOrderStatus.PLACED and any(r.store_order_id == so.id for r in order.removals)
    ]
    owes = order.payment_status == PaymentStatus.PENDING and order.status != OrderStatus.CANCELLED
    otp = None
    if order.status == OrderStatus.OUT_FOR_DELIVERY:  # delivery partner ko batane ke liye, sirf raaste me dikhta hai
        live = await db.scalar(select(Delivery).where(Delivery.order_id == order.id, Delivery.status == "OUT_FOR_DELIVERY"))
        if live is not None:
            otp = delivery_otp(settings.jwt_secret, live.id)
    return OrderOut(
        id=order.id, order_number=order.order_number, status=order.status, payment_method=order.payment_method,
        payment_status=order.payment_status,
        address=AddressSnapshotOut(
            receiver_name=order.receiver_name, receiver_phone=order.receiver_phone, address_line=order.address_line,
            landmark=order.landmark, latitude=float(order.latitude), longitude=float(order.longitude),
        ),
        items_subtotal=float(order.items_subtotal), delivery_fee=float(order.delivery_fee), total=float(order.total),
        original_items_subtotal=float(order.original_items_subtotal), original_total=float(order.original_total),
        removed_total=float(removed_total), delivery_fee_added=float(fee_added), can_cancel=can_cancel,
        seller_can_accept_after=max(waits) if waits else None, amount_due=float(order.total) if owes else 0.0,
       delivery_otp=otp, removed_items=removed_items, notice=notice,
        note=order.note, created_at=order.created_at, stores=stores,
        history=[
            StatusHistoryOut(
                store_order_id=h.store_order_id, from_status=h.from_status, to_status=h.to_status, actor_role=h.actor_role,
                note=h.note, created_at=h.created_at,
            )
            for h in history
        ],
    )


async def _get_own(db: AsyncSession, user: User, order_id: uuid.UUID, *, for_update: bool = False) -> Order:
    q = select(Order).where(Order.id == order_id, Order.user_id == user.id)
    if for_update:
        q = q.with_for_update()
    order = await db.scalar(q)
    if order is None:  # doosre ka order bhi 404
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")
    return order


async def get_order(db: AsyncSession, user: User, order_id: uuid.UUID, lang: str) -> OrderOut:
    return await _order_out(db, await _get_own(db, user, order_id), lang)


async def list_orders(db: AsyncSession, user: User, limit: int, offset: int) -> list[OrderSummary]:
    orders = (
        await db.scalars(
            select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc(), Order.id).limit(limit).offset(offset)
        )
    ).all()
    out = []
    for o in orders:
        removed_ids = {r.order_item_id for r in o.removals}
        out.append(
            OrderSummary(
                id=o.id, order_number=o.order_number, status=o.status, payment_method=o.payment_method,
                payment_status=o.payment_status, total=float(o.total), has_removed_items=bool(removed_ids),
                store_names=[so.store_name for so in o.store_orders],
                item_count=sum(i.quantity for so in o.store_orders for i in so.items if i.id not in removed_ids),
                created_at=o.created_at,
            )
        )
    return out


# ---------------- Cancel ----------------


async def cancel_order(db: AsyncSession, user: User, order_id: uuid.UUID, reason: str | None, lang: str) -> OrderOut:
    """Customer tab tak cancel kar sakta hai jab tak koi bhi seller ne order accept nahi kiya."""
    await _lock_user(db, user)
    order = await _get_own(db, user, order_id, for_update=True)
    if order.status == OrderStatus.CANCELLED:  # dobara cancel: error nahi, wahi haal
        return await _order_out(db, order, lang)

    # Seller ne jo hissa reject kiya ya jo item hataya, uska stock pehle hi wapas aa chuka hai: use dobara na chhedo
        removed_ids = {r.order_item_id for r in order.removals}
    live = [so for so in order.store_orders if so.status != StoreOrderStatus.REJECTED]
    if not _can_cancel(order):
        raise api_error(409, "ORDER_CANNOT_CANCEL", "Ab ye order cancel nahi ho sakta.")

    note = (reason or "").strip() or None
    previous = order.status
    qty_by_product: dict[uuid.UUID, int] = {}
    for so in live:
        db.add(_history(order.id, StoreOrderStatus.CANCELLED, user, "CUSTOMER", store_order_id=so.id, from_status=so.status, note=note))
        so.status = StoreOrderStatus.CANCELLED
        for i in so.items:
            if i.id not in removed_ids:
                qty_by_product[i.product_id] = qty_by_product.get(i.product_id, 0) + i.quantity

    for pid in sorted(qty_by_product):  # stock wapas (ORDER_CANCEL)
        await adjust_stock(db, pid, qty_by_product[pid], StockReason.ORDER_CANCEL, actor=user, note=f"order {order.order_no} cancel")

    order.status = OrderStatus.CANCELLED
    if order.payment_status == PaymentStatus.PENDING:
        order.payment_status = PaymentStatus.NOT_REQUIRED  # paisa liya hi nahi gaya tha
    db.add(_history(order.id, OrderStatus.CANCELLED, user, "CUSTOMER", from_status=previous, note=note))
    await cancel_live_delivery(db, order.id, "customer ne order cancel kiya")  # partner ko free karo
    await db.commit()