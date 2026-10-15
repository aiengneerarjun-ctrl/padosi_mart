"""Online payment (Cashfree): payment shuru karna, webhook, refund, bina-payment order ka expiry.

Safar:
 1. Customer ONLINE order karta hai -> order PLACED + payment PENDING (stock ruk jaata hai). Seller / partner ko ye order dikhta nahi.
 2. POST /orders/{id}/pay -> Cashfree me order banta hai, app ko payment_session_id milta hai (SDK se payment).
 3. Cashfree webhook (PAYMENT_SUCCESS) -> hamari taraf payment PAID, order CONFIRMED, sellers ko "naya order".
    Webhook ko sach maanne se pehle signature (RAW body par) check hota hai. Ek event ek hi baar chalta hai (payment_events).
 4. payment_window_minutes me payment na ho to order cancel + stock wapas (expire_unpaid; cron / admin se chalta hai).
    Agar payment baad me aa jaaye to paisa apne aap wapas (refund LATE_PAYMENT).
 5. Paid ONLINE order cancel ho, ya seller items hataye -> refund (poora / hataye gaye hisse jitna). Cashfree ko bhejna COMMIT KE BAAD
    (process_pending_refunds), taaki bahar ka call fail ho to bhi hamara hisaab sahi rahe; fail hua refund PENDING rehta hai aur
    admin se retry ho sakta hai.
 6. Admin kabhi bhi refund de sakta hai (jaise fail hui delivery), kul refund paid se zyada kabhi nahi.
Lock ka kram: Order row, phir payment / refund rows.
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import api_error
from app.models import Order, OrderStatusHistory, Payment, PaymentEvent, Refund, User
from app.models.order import OrderStatus, PaymentMethod, PaymentStatus
from app.schemas.payment import PaymentDetailOut, PaymentSessionOut, RefundOut
from app.services import cashfree, notification
from app.services.audit import write_audit
from app.services.cashfree import CashfreeError

log = logging.getLogger("padosi.payment")
CENT = Decimal("0.01")


def pay_until(order: Order) -> datetime:
    return order.created_at + timedelta(minutes=settings.payment_window_minutes)


async def _lock_order(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Order | None:
    q = select(Order).where(Order.id == order_id)
    if user_id is not None:
        q = q.where(Order.user_id == user_id)
    return await db.scalar(q.with_for_update().execution_options(populate_existing=True))


async def _lock_payment(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    return await db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update().execution_options(populate_existing=True))


def _session_out(order_id: uuid.UUID, p: Payment) -> PaymentSessionOut:
    return PaymentSessionOut(
        order_id=order_id, provider_order_id=p.provider_order_id, payment_session_id=p.payment_session_id, amount=float(p.amount),
        environment=settings.cashfree_env, expires_at=p.expires_at,
    )


# ---------------- 2. payment shuru ----------------
async def start_payment(db: AsyncSession, user: User, order_id: uuid.UUID) -> PaymentSessionOut:
    if not cashfree.enabled():
        raise api_error(409, "PAYMENT_METHOD_NOT_AVAILABLE", "Ye payment tareeka abhi available nahi hai.")
    order = await _lock_order(db, order_id, user.id)
    if order is None:
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")
    if order.payment_method != PaymentMethod.ONLINE:
        raise api_error(409, "PAYMENT_NOT_ALLOWED", "Is order ke liye payment nahi ho sakta.")
    if order.payment_status == PaymentStatus.PAID:
        raise api_error(409, "PAYMENT_ALREADY_PAID", "Is order ka payment ho chuka hai.")
    if order.status != OrderStatus.PLACED or order.payment_status != PaymentStatus.PENDING:
        raise api_error(409, "PAYMENT_NOT_ALLOWED", "Is order ke liye payment nahi ho sakta.")
    expires_at = pay_until(order)
    if datetime.now(timezone.utc) >= expires_at:
        raise api_error(409, "PAYMENT_EXPIRED", "Payment ka samay nikal gaya. Naya order karein.")

    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    if payment is None:
        payment = Payment(order_id=order.id, provider_order_id=f"PD{order.order_no}", amount=order.total, expires_at=expires_at)
        db.add(payment)
        await db.flush()
    payment_id, provider_order_id, amount = payment.id, payment.provider_order_id, payment.amount
    order_pk, order_number, receiver = order.id, order.order_number, order.receiver_name
    if payment.payment_session_id:
        out = _session_out(order_pk, payment)
        await db.commit()
        return out
    await db.commit()  # lock chhodo; bahar ka call lock rakhkar nahi

    try:
        try:
            data = await cashfree.create_order(
                order_id=provider_order_id, amount=amount, customer_id=user.id.hex, phone=user.phone, name=receiver,
                expires_at=expires_at, note=f"Padosi order {order_number}",
            )
        except CashfreeError as e:
            if e.status != 409:  # 409 = Cashfree me ye order pehle ban chuka hai: uska session le lo
                raise
            data = await cashfree.get_order(provider_order_id)
    except CashfreeError as e:
        log.error("payment start fail order=%s: %s", provider_order_id, e)
        raise api_error(502, "PAYMENT_PROVIDER_ERROR", "Payment shuru nahi ho paaya. Thodi der baad dobara koshish karein.")
    session = data.get("payment_session_id")
    if not session:
        raise api_error(502, "PAYMENT_PROVIDER_ERROR", "Payment shuru nahi ho paaya. Thodi der baad dobara koshish karein.")
    payment = await _lock_payment(db, payment_id)
    payment.cf_order_id = str(data.get("cf_order_id") or "") or None
    payment.payment_session_id = session
    out = _session_out(order_pk, payment)
    await db.commit()
    return out


# ---------------- 3. webhook ----------------
def _event_key(etype: str, data: dict, raw: bytes) -> str:
    pay, ref = data.get("payment") or {}, data.get("refund") or {}
    if etype.startswith("PAYMENT") and pay.get("cf_payment_id"):
        return f"{etype}:{pay['cf_payment_id']}:{pay.get('payment_status')}"[:160]
    if etype.startswith("REFUND") and ref.get("refund_id"):
        return f"{etype}:{ref['refund_id']}:{ref.get('refund_status')}"[:160]
    return "raw:" + hashlib.sha256(raw).hexdigest()


async def handle_cashfree_webhook(db: AsyncSession, raw: bytes, timestamp: str | None, signature: str | None) -> str:
    if not cashfree.verify_signature(timestamp, raw, signature):
        raise api_error(401, "INVALID_SIGNATURE", "Signature galat hai.")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        raise api_error(400, "INVALID_WEBHOOK", "Webhook ka body sahi nahi hai.")
    etype = str(payload.get("type") or "")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

    inserted = await db.scalar(
        pg_insert(PaymentEvent).values(id=uuid.uuid4(), event_key=_event_key(etype, data, raw), event_type=etype[:60], payload=payload)
        .on_conflict_do_nothing(index_elements=["event_key"]).returning(PaymentEvent.id)
    )
    if inserted is None:  # ye event pehle chal chuka
        await db.rollback()
        return "duplicate"
    order_id = None
    if etype == "PAYMENT_SUCCESS_WEBHOOK":
        order_id = await _on_payment_success(db, data)
    elif etype == "REFUND_STATUS_WEBHOOK":
        await _on_refund_status(db, data)
    await db.commit()  # event + uska asar ek saath
    if order_id is not None:  # late payment se bana refund Cashfree ko bhejo
        await process_pending_refunds(db, order_id=order_id)
    return "ok"


async def _on_payment_success(db: AsyncSession, data: dict) -> uuid.UUID | None:
    pay_d, ord_d = data.get("payment") or {}, data.get("order") or {}
    if str(pay_d.get("payment_status")) != "SUCCESS":
        return None
    payment = await db.scalar(select(Payment).where(Payment.provider_order_id == str(ord_d.get("order_id"))))
    if payment is None:
        log.warning("webhook: anjaan order %s", ord_d.get("order_id"))
        return None
    order = await _lock_order(db, payment.order_id)
    payment = await _lock_payment(db, payment.id)
    if payment.status == "PAID":
        return None
    paid = Decimal(str(pay_d.get("payment_amount", ord_d.get("order_amount", "0")))).quantize(CENT)
    if paid != payment.amount:  # galat rakam: kuch mat badlo (event save rehta hai, admin dekh sakta hai)
        log.error("webhook: rakam alag order=%s payment=%s expected=%s", payment.provider_order_id, paid, payment.amount)
        return None
    payment.status = "PAID"
    payment.cf_payment_id = str(pay_d.get("cf_payment_id") or "") or None
    payment.paid_at = datetime.now(timezone.utc)
    if order.status == OrderStatus.PLACED and order.payment_status == PaymentStatus.PENDING:
        order.payment_status = PaymentStatus.PAID
        order.status = OrderStatus.CONFIRMED
        db.add(OrderStatusHistory(
            order_id=order.id, from_status=OrderStatus.PLACED, to_status=OrderStatus.CONFIRMED, actor_id=None, actor_role="SYSTEM", note="ONLINE payment mila",
        ))
        await notification.notify_sellers_new_order(db, order)
        return None
    # Payment tab aaya jab order cancel ho chuka tha: paisa wapas
    order.payment_status = PaymentStatus.PAID
    await request_refund(db, order, None, "LATE_PAYMENT", "order cancel hone ke baad payment aaya", None)
    return order.id


async def _on_refund_status(db: AsyncSession, data: dict) -> None:
    ref = data.get("refund") or {}
    r = await db.scalar(select(Refund).where(Refund.refund_id == str(ref.get("refund_id"))).with_for_update().execution_options(populate_existing=True))
    if r is not None:
        await _apply_refund_result(db, r, ref.get("refund_status"), ref.get("cf_refund_id"))


# ---------------- refund ----------------
async def _refunded(db: AsyncSession, payment_id: uuid.UUID, statuses=("PENDING", "SUCCESS")) -> Decimal:
    v = await db.scalar(select(func.coalesce(func.sum(Refund.amount), 0)).where(Refund.payment_id == payment_id, Refund.status.in_(statuses)))
    return Decimal(str(v))


async def request_refund(
    db: AsyncSession, order: Order, amount: Decimal | None, reason_code: str, note: str | None, actor_id: uuid.UUID | None
) -> Refund | None:
    """Refund ka record banao (Cashfree ko bhejna commit ke baad). amount None = jitna bacha hai sab. Kabhi paid se zyada nahi.
    Caller ne Order row lock ki hui honi chahiye."""
    payment = await db.scalar(
        select(Payment).where(Payment.order_id == order.id, Payment.status == "PAID").with_for_update().execution_options(populate_existing=True)
    )
    if payment is None:
        return None
    remaining = payment.amount - await _refunded(db, payment.id)
    amount = remaining if amount is None else min(Decimal(amount).quantize(CENT), remaining)
    if amount <= 0:
        return None
    r = Refund(
        order_id=order.id, payment_id=payment.id, refund_id="RF" + uuid.uuid4().hex[:24], amount=amount, reason_code=reason_code,
        note=(note or "")[:300] or None, actor_id=actor_id,
    )
    db.add(r)
    if remaining - amount == 0:  # sab wapas ho raha hai
        order.payment_status = PaymentStatus.REFUND_PENDING
    return r


def _map_status(provider_status: str | None) -> str:
    s = (provider_status or "").upper()
    if s == "SUCCESS":
        return "SUCCESS"
    if s in ("CANCELLED", "FAILED"):
        return "FAILED"
    return "PENDING"


async def _apply_refund_result(db: AsyncSession, r: Refund, provider_status: str | None, cf_refund_id) -> None:
    """Refund ka naya status likho (SUCCESS ko wapas nahi badalte). Poora paisa wapas ho gaya to order REFUNDED."""
    r.provider_status = (provider_status or r.provider_status or "")[:30] or None
    if cf_refund_id:
        r.cf_refund_id = str(cf_refund_id)[:40]
    if r.status != "SUCCESS":
        r.status = _map_status(provider_status)
    if r.status == "SUCCESS":
        paid = await db.scalar(select(Payment.amount).where(Payment.id == r.payment_id))
        if await _refunded(db, r.payment_id, ("SUCCESS",)) >= paid:
            await db.execute(
                update(Order).where(Order.id == r.order_id, Order.payment_status.in_([PaymentStatus.PAID, PaymentStatus.REFUND_PENDING]))
                .values(payment_status=PaymentStatus.REFUNDED)
            )


async def process_pending_refunds(db: AsyncSession, order_id: uuid.UUID | None = None, refund_pk: uuid.UUID | None = None) -> int:
    """Jo refund Cashfree ko abhi nahi gaye (PENDING, cf_refund_id khali) unhe bhejo. Bahar ka call fail ho to refund PENDING hi rehta hai.
    Ek hi refund do jagah se ek saath nahi jaata (SKIP LOCKED). Lautata hai: kitne Cashfree ne le liye."""
    if not cashfree.enabled():
        return 0
    q = select(Refund).where(Refund.status == "PENDING", Refund.cf_refund_id.is_(None))
    if order_id is not None:
        q = q.where(Refund.order_id == order_id)
    if refund_pk is not None:
        q = q.where(Refund.id == refund_pk)
    refunds = (await db.scalars(q.order_by(Refund.created_at).with_for_update(skip_locked=True).execution_options(populate_existing=True))).all()
    sent = 0
    for r in refunds:
        provider_order_id = await db.scalar(select(Payment.provider_order_id).where(Payment.id == r.payment_id))
        try:
            data = await cashfree.create_refund(order_id=provider_order_id, refund_id=r.refund_id, amount=r.amount, note=r.reason_code)
        except CashfreeError as e:
            log.error("refund bhejna fail %s: %s", r.refund_id, e)
            r.provider_status = f"ERR_{e.status or 'NET'}"
            continue
        await _apply_refund_result(db, r, data.get("refund_status"), data.get("cf_refund_id") or "PENDING-ID")
        if r.status != "FAILED":
            sent += 1
            row = (await db.execute(select(Order.user_id, Order.order_no).where(Order.id == r.order_id))).one()
            notification.add(db, row.user_id, "REFUND_INITIATED", {"order_no": f"PD{row.order_no}", "amount": f"{r.amount:.2f}"}, r.order_id)
    await db.commit()
    return sent


# ---------------- 4. bina payment ke order ----------------
async def expire_unpaid(db: AsyncSession, limit: int = 200) -> int:
    """Jin ONLINE orders ka payment samay (payment_window_minutes) me nahi hua unhe cancel karo, stock wapas. Kitne hue, wo lautata hai."""
    from app.services import order as order_service  # order.py bhi payment.py ko import karta hai

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.payment_window_minutes)
    ids = (
        await db.scalars(
            select(Order.id).where(
                Order.payment_method == PaymentMethod.ONLINE, Order.status == OrderStatus.PLACED,
                Order.payment_status == PaymentStatus.PENDING, Order.created_at < cutoff,
            ).order_by(Order.created_at).limit(limit)
        )
    ).all()
    done = 0
    for oid in ids:
        try:
            if await order_service.cancel_unpaid(db, oid):
                done += 1
        except Exception:  # ek kharab order baaki ko na roke
            await db.rollback()
            log.exception("expire fail order=%s", oid)
    return done


# ---------------- admin ----------------
def _refund_out(r: Refund, order_no: int) -> RefundOut:
    return RefundOut(
        id=r.id, order_id=r.order_id, order_number=f"PD{order_no}", refund_id=r.refund_id, amount=float(r.amount), status=r.status,
        reason_code=r.reason_code, note=r.note, cf_refund_id=r.cf_refund_id, provider_status=r.provider_status,
        created_at=r.created_at, updated_at=r.updated_at,
    )


async def admin_detail(db: AsyncSession, order_id: uuid.UUID) -> PaymentDetailOut:
    row = (
        await db.execute(select(Payment, Order.order_no).join(Order, Order.id == Payment.order_id).where(Payment.order_id == order_id).execution_options(populate_existing=True))
    ).first()
    if row is None:
        raise api_error(404, "PAYMENT_NOT_FOUND", "Is order ka payment nahi mila.")
    p, order_no = row
    refunds = (await db.scalars(select(Refund).where(Refund.order_id == order_id).order_by(Refund.created_at, Refund.id).execution_options(populate_existing=True))).all()
    refunded = await _refunded(db, p.id)
    return PaymentDetailOut(
        order_id=order_id, order_number=f"PD{order_no}", provider_order_id=p.provider_order_id, amount=float(p.amount), status=p.status,
        cf_payment_id=p.cf_payment_id, paid_at=p.paid_at, refunded_total=float(refunded),
        refundable=float(p.amount - refunded) if p.status == "PAID" else 0.0, refunds=[_refund_out(r, order_no) for r in refunds],
    )


async def admin_refund(
    db: AsyncSession, admin: User, request: Request, order_id: uuid.UUID, amount: Decimal, note: str
) -> PaymentDetailOut:
    order = await _lock_order(db, order_id)
    if order is None:
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")
    payment = await db.scalar(select(Payment).where(Payment.order_id == order_id, Payment.status == "PAID"))
    if payment is None:
        raise api_error(404, "PAYMENT_NOT_FOUND", "Is order ka paid payment nahi mila.")
    remaining = payment.amount - await _refunded(db, payment.id)
    if amount.quantize(CENT) > remaining:
        raise api_error(409, "REFUND_EXCEEDS_PAID", "Itna paisa wapas nahi kiya ja sakta.")
    r = await request_refund(db, order, amount, "ADMIN", note, admin.id)
    write_audit(
        db, actor=admin, action="payment.admin_refund", target_type="order", target_id=order_id,
        old={"refundable": str(remaining)}, new={"refundable": str(remaining - amount), "amount": str(amount)}, reason=note, request=request,
    )
    await db.commit()
    await process_pending_refunds(db, refund_pk=r.id)
    return await admin_detail(db, order_id)


async def admin_list_refunds(db: AsyncSession, status: str | None, limit: int, offset: int) -> list[RefundOut]:
    q = select(Refund, Order.order_no).join(Order, Order.id == Refund.order_id)
    if status:
        q = q.where(Refund.status == status)
    q = q.order_by(Refund.created_at if status == "PENDING" else Refund.created_at.desc(), Refund.id).limit(limit).offset(offset)
    return [_refund_out(r, no) for r, no in (await db.execute(q.execution_options(populate_existing=True))).all()]


async def admin_retry_refund(db: AsyncSession, refund_pk: uuid.UUID) -> RefundOut:
    row = (await db.execute(select(Refund, Order.order_no).join(Order, Order.id == Refund.order_id).where(Refund.id == refund_pk))).first()
    if row is None:
        raise api_error(404, "REFUND_NOT_FOUND", "Refund nahi mila.")
    await process_pending_refunds(db, refund_pk=refund_pk)
    row = (await db.execute(select(Refund, Order.order_no).join(Order, Order.id == Refund.order_id).where(Refund.id == refund_pk).execution_options(populate_existing=True))).one()
    return _refund_out(row[0], row[1])