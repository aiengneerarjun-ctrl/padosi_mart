"""Notifications: har user (customer / seller / delivery partner) ka inbox.

- Notification business kaam ke SAATH usi transaction me save hoti hai (add / event hook), isliye order ho aur notification kho jaye
  ya notification ho aur order na ho, aisa nahi hota.
- Text yahan save nahi hota; code + params save hote hain, padhte waqt user ki bhasha (en/hi/bho) me banta hai.
- Customer ko order ka status badalne ki notification EK jagah se aati hai: OrderStatusHistory me order-level row jodte hi
  (neeche wala event). Isse kisi nayi jagah se status badalne par notification bhoolna mumkin nahi.
  Sirf wahi row jisme status SACH me badla (from != to) aur jo customer ke kaam ki ho; customer ne khud cancel kiya to nahi.
- Baaki (seller ko naya order, customer ko items hatne ki khabar, partner ko payout) us kaam ke code se `add()` bulakar.
- Bhejna (SMS / push) abhi nahi: ye sirf app ke andar ka inbox hai. Baad me provider isi table ko padhkar bhejega.
"""
import uuid
from collections import defaultdict

from sqlalchemy import event, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import MESSAGES
from app.models import Notification, Order, OrderStatusHistory, User
from app.models.order import OrderStatus
from app.schemas.notification import NotificationOut

# Order-level status -> customer ko kaunsi notification
ORDER_STATUS_NOTIFICATIONS = {
    OrderStatus.SELLER_ACCEPTED: "ORDER_ACCEPTED",
    OrderStatus.DELIVERY_ASSIGNED: "ORDER_PARTNER_ASSIGNED",
    OrderStatus.OUT_FOR_DELIVERY: "ORDER_OUT_FOR_DELIVERY",
    OrderStatus.DELIVERED: "ORDER_DELIVERED",
    OrderStatus.CANCELLED: "ORDER_CANCELLED",
    OrderStatus.FAILED_DELIVERY: "ORDER_FAILED_DELIVERY",
}


def add(db: AsyncSession, user_id: uuid.UUID, code: str, params: dict | None = None, order_id: uuid.UUID | None = None) -> None:
    """Notification ko usi transaction me jodo (commit business kaam wala karega)."""
    db.add(Notification(user_id=user_id, code=code, params=params or {}, order_id=order_id))


@event.listens_for(OrderStatusHistory, "after_insert")
def _notify_customer_on_status_change(mapper, connection, h: OrderStatusHistory) -> None:
    if h.store_order_id is not None or h.from_status == h.to_status:  # dukaan-level ya "sirf total badla" wali row
        return
    code = ORDER_STATUS_NOTIFICATIONS.get(h.to_status)
    if code is None:
        return
    row = connection.execute(select(Order.user_id, Order.order_no).where(Order.id == h.order_id)).first()
    if row is None or (h.actor_id is not None and h.actor_id == row.user_id):  # customer ne khud kiya to use batana nahi
        return
    connection.execute(
        insert(Notification.__table__).values(id=uuid.uuid4(), user_id=row.user_id, code=code, params={"order_no": f"PD{row.order_no}"}, order_id=h.order_id)
    )


class _Params(defaultdict):
    def __missing__(self, key):  # khali jagah ka param na mile to {key} hi dikhe, error nahi
        return "{" + key + "}"


def _text(key: str, lang: str, fallback: str) -> str:
    entry = MESSAGES.get(key)
    return (entry.get(lang) or entry["en"]) if entry else fallback


def render(n: Notification, lang: str) -> NotificationOut:
    params = _Params(str, n.params or {})
    return NotificationOut(
        id=n.id, code=n.code,
        title=_text(f"NOTIF_{n.code}_TITLE", lang, n.code).format_map(params),  # text na mile to code hi dikhe
        body=_text(f"NOTIF_{n.code}_BODY", lang, "").format_map(params),
        order_id=n.order_id, is_read=n.read_at is not None, created_at=n.created_at, read_at=n.read_at,
    )


async def list_mine(db: AsyncSession, user: User, unread_only: bool, limit: int, offset: int, lang: str) -> list[NotificationOut]:
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    q = q.order_by(Notification.created_at.desc(), Notification.id).limit(limit).offset(offset)
    return [render(n, lang) for n in await db.scalars(q)]


async def unread_count(db: AsyncSession, user: User) -> int:
    return await db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))) or 0


async def mark_read(db: AsyncSession, user: User, notification_id: uuid.UUID, lang: str) -> NotificationOut:
    """Padhi hui mark karo. Doosre ki notification = 404. Pehle se padhi hui ho to waisi hi wapas (padhne ka time nahi badalta)."""
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    n = await db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id).execution_options(populate_existing=True)
    )
    if n is None:
        raise api_error(404, "NOTIFICATION_NOT_FOUND", "Notification nahi mili.")
    await db.commit()
    return render(n, lang)


async def mark_all_read(db: AsyncSession, user: User) -> int:
    res = await db.execute(
        update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=func.now())
    )
    await db.commit()
    return res.rowcount or 0