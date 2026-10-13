"""Fail hui delivery ka saaman dukaan ko wapas: record + stock wapas.

- Delivery fail hote hi har zinda dukaan-hisse ki ek PENDING row banti hai (delivery_progress.mark_failed).
- Dukaan (seller) saaman mil jaane par "received" karta hai. Seller na kare / suspended ho to Super Admin kar sakta hai.
- Kirana me, saaman theek ho (stock_ok) to stock wapas judta hai (inventory.adjust_stock, reason RETURN).
  Restaurant ka bana hua khana wapas stock me nahi judta. stock_ok=False me bhi nahi judta.
- Jo item seller pehle hi hata chuka tha uska stock tab hi wapas aa gaya tha, wo dobara nahi judta.
- Wahi confirm dobara bhejna error nahi (jaisa hai waisa hi wapas; stock dobara nahi judta).
Lock ka kram wahi: pehle Order row, phir return row. Stock product_id ke kram me.
"""
import uuid

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import localized
from app.models import Delivery, Order, Seller, Store, StoreOrder, StoreOrderReturn, User
from app.models.catalog import StockReason
from app.models.delivery import ReturnStatus
from app.models.seller import SellerStatus
from app.schemas.delivery_return import ReturnItemOut, ReturnOut
from app.services.audit import write_audit
from app.services.delivery_assignment import _load_order
from app.services.delivery_rules import should_restock, stock_to_return
from app.services.inventory import adjust_stock


def _out(ret: StoreOrderReturn, so: StoreOrder, order: Order, fail_reason: str | None, lang: str) -> ReturnOut:
    removed = {r.order_item_id for r in order.removals}
    return ReturnOut(
        store_order_id=so.id, order_id=order.id, order_number=order.order_number, store_id=so.store_id, store_name=so.store_name,
        status=ret.status, was_picked_up=ret.was_picked_up, fail_reason=fail_reason,
        items=[ReturnItemOut(name=localized(i, lang), quantity=i.quantity, selling_unit=i.selling_unit) for i in so.items if i.id not in removed],
        restocked=ret.restocked, received_at=ret.received_at, received_role=ret.received_role, note=ret.note, created_at=ret.created_at,
    )


def _query():
    return (
        select(StoreOrderReturn, StoreOrder, Order, Delivery.fail_reason)
        .join(StoreOrder, StoreOrder.id == StoreOrderReturn.store_order_id)
        .join(Order, Order.id == StoreOrderReturn.order_id)
        .join(Delivery, Delivery.id == StoreOrderReturn.delivery_id)
    )


async def _list(db: AsyncSession, status: str | None, seller: Seller | None, limit: int, offset: int, lang: str) -> list[ReturnOut]:
    q = _query()
    if seller is not None:
        q = q.where(StoreOrder.seller_id == seller.id)
    if status:
        q = q.where(StoreOrderReturn.status == status)
    # Baaki wale sabse purane pehle (jo sabse zyada intezaar me hai), mil chuke wale sabse naye pehle
    q = q.order_by(StoreOrderReturn.created_at if status == ReturnStatus.PENDING else StoreOrderReturn.created_at.desc(), StoreOrderReturn.id)
    rows = (await db.execute(q.limit(limit).offset(offset).execution_options(populate_existing=True))).all()
    return [_out(ret, so, order, fr, lang) for ret, so, order, fr in rows]


async def seller_list(db: AsyncSession, seller: Seller, status: str | None, limit: int, offset: int, lang: str) -> list[ReturnOut]:
    return await _list(db, status, seller, limit, offset, lang)


async def admin_list(db: AsyncSession, status: str | None, limit: int, offset: int, lang: str) -> list[ReturnOut]:
    return await _list(db, status, None, limit, offset, lang)


async def _one(db: AsyncSession, store_order_id: uuid.UUID, lang: str) -> ReturnOut:
    ret, so, order, fr = (await db.execute(_query().where(StoreOrderReturn.store_order_id == store_order_id).execution_options(populate_existing=True))).one()
    return _out(ret, so, order, fr, lang)


async def receive(
    db: AsyncSession, user: User, store_order_id: uuid.UUID, *, stock_ok: bool, note: str | None, lang: str,
    seller: Seller | None = None, request: Request | None = None,
) -> ReturnOut:
    """seller diya = dukaan khud confirm kar rahi hai (sirf apna hissa). seller None = Super Admin (audit log likhta hai)."""
    if seller is not None and seller.status != SellerStatus.ACTIVE:
        raise api_error(403, "SELLER_NOT_ACTIVE", "Aapka seller account abhi active nahi hai.")
    row = (await db.execute(select(StoreOrder.order_id, StoreOrder.seller_id, StoreOrder.store_id).where(StoreOrder.id == store_order_id))).first()
    if row is None or (seller is not None and row.seller_id != seller.id):  # doosre ka hissa = 404
        raise api_error(404, "RETURN_NOT_FOUND", "Wapas aane wala saaman nahi mila.")

    order = await _load_order(db, row.order_id, lock=True)  # pehle Order row lock
    ret = await db.scalar(
        select(StoreOrderReturn).where(StoreOrderReturn.store_order_id == store_order_id).with_for_update().execution_options(populate_existing=True)
    )
    if ret is None:
        raise api_error(404, "RETURN_NOT_FOUND", "Wapas aane wala saaman nahi mila.")
    if ret.status == ReturnStatus.RECEIVED:  # wahi dobara: kuch nahi badalta, stock dobara nahi judta
        return await _one(db, store_order_id, lang)

    so = next(s for s in order.store_orders if s.id == store_order_id)
    store_type = await db.scalar(select(Store.store_type).where(Store.id == row.store_id))
    restock = should_restock(store_type, stock_ok)
    if restock:
        wanted = stock_to_return([(i.id, i.product_id, i.quantity) for i in so.items], {r.order_item_id for r in order.removals})
        for pid in sorted(wanted):  # product_id ke kram me (deadlock se bachne ke liye)
            await adjust_stock(db, pid, wanted[pid], StockReason.RETURN, actor=user, note=f"order {order.order_no} delivery fail, saaman wapas")

    now = await db.scalar(select(func.now()))  # database ki ghadi; status badalne se PEHLE (beech me autoflush se constraint na tute)
    ret.status = ReturnStatus.RECEIVED
    ret.received_at = now
    ret.received_by = user.id
    ret.received_role = "SELLER" if seller is not None else "SUPER_ADMIN"
    ret.restocked = restock
    ret.note = note
    if seller is None:
        write_audit(
            db, actor=user, action="delivery_return.admin_receive", target_type="store_order", target_id=store_order_id,
            old={"status": "PENDING"}, new={"status": "RECEIVED", "restocked": restock}, reason=note, request=request,
        )
    await db.commit()
    return await _one(db, store_order_id, lang)