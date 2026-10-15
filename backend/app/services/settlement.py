"""Seller ka hisaab: commission aur settlement.

- Delivery poori hote hi har (zinda) dukaan-hisse par platform ka commission likh diya jaata hai:
  commission = dukaan ka items_subtotal (seller ke hataye items ke baad) x rate%. Rate dukaan ke type (KIRANA / RESTAURANT) se,
  Super Admin tay karta hai. Baad me rate badle to purana hisaab nahi badalta. Fail / cancel / reject hue hisse par kuch nahi.
- Seller ko dena baaki = kul bikri - kul commission - admin ne jitna diya. Admin seller ko paisa deta hai aur "paid" entry likhta hai
  (seller_payouts, badalta nahi). Paid kabhi kamai se zyada nahi; galti hui to negative sudhaar + note.
- COD cash ka hisaab alag hai (partner admin ko cash jama karta hai); seller ka paisa us cash se nahi kategta.
Lock: seller row (payout likhte waqt), taaki do admin ek saath galat hisaab na likh dein.
"""
import uuid
from decimal import Decimal

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Delivery, Order, Seller, SellerPayout, SettlementSettings, Store, StoreOrder, User
from app.models.delivery import DeliveryStatus
from app.models.order import StoreOrderStatus
from app.schemas.settlement import (
    AdminSettlementRowOut, SellerPayoutOut, SettlementOrderOut, SettlementRatesOut, SettlementSummaryOut,
)
from app.services import notification
from app.services.audit import write_audit
from app.services.delivery_rules import deposit_problem
from app.services.settlement_rules import commission_amount, rate_for_store_type

INACTIVE = (StoreOrderStatus.REJECTED, StoreOrderStatus.CANCELLED)
RECENT = 20


async def _settings(db: AsyncSession, *, lock: bool = False) -> SettlementSettings | None:
    q = select(SettlementSettings).where(SettlementSettings.id == 1).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    return await db.scalar(q)


async def apply_commission(db: AsyncSession, order: Order) -> None:
    """Delivery poori hone par (usi transaction me) har zinda dukaan-hisse par abhi ka commission fix karo. Pehle se likha ho to chhod do."""
    s = await _settings(db)
    live = [so for so in order.store_orders if so.status not in INACTIVE and so.commission_amount is None]
    if not live:
        return
    types = dict((await db.execute(select(Store.id, Store.store_type).where(Store.id.in_({so.store_id for so in live})))).all())
    for so in live:
        rate = rate_for_store_type(types.get(so.store_id), s.kirana_rate if s else Decimal("0"), s.restaurant_rate if s else Decimal("0"))
        so.commission_rate = rate
        so.commission_amount = commission_amount(so.items_subtotal, rate)


async def get_rates(db: AsyncSession) -> SettlementRatesOut:
    s = await _settings(db)
    if s is None:
        raise api_error(404, "NOT_FOUND", "Rate settings nahi mili.")
    return SettlementRatesOut(kirana_rate=float(s.kirana_rate), restaurant_rate=float(s.restaurant_rate), updated_at=s.updated_at)


async def set_rates(
    db: AsyncSession, admin: User, request: Request, kirana_rate: Decimal | None, restaurant_rate: Decimal | None, reason: str
) -> SettlementRatesOut:
    s = await _settings(db, lock=True)
    if s is None:
        raise api_error(404, "NOT_FOUND", "Rate settings nahi mili.")
    old = {"kirana_rate": str(s.kirana_rate), "restaurant_rate": str(s.restaurant_rate)}
    if kirana_rate is not None:
        s.kirana_rate = kirana_rate
    if restaurant_rate is not None:
        s.restaurant_rate = restaurant_rate
    s.updated_by = admin.id
    write_audit(
        db, actor=admin, action="settlement.set_rates", target_type="settlement_settings", target_id="rates",
        old=old, new={"kirana_rate": str(s.kirana_rate), "restaurant_rate": str(s.restaurant_rate)}, reason=reason, request=request,
    )
    await db.commit()
    return await get_rates(db)


async def _totals(db: AsyncSession, seller_id: uuid.UUID) -> tuple[Decimal, Decimal, Decimal]:
    """(kul bikri, kul commission, kul paid)"""
    row = (
        await db.execute(
            select(func.coalesce(func.sum(StoreOrder.items_subtotal), 0), func.coalesce(func.sum(StoreOrder.commission_amount), 0))
            .where(StoreOrder.seller_id == seller_id, StoreOrder.commission_amount.is_not(None))
        )
    ).one()
    paid = await db.scalar(select(func.coalesce(func.sum(SellerPayout.amount), 0)).where(SellerPayout.seller_id == seller_id))
    return Decimal(str(row[0])), Decimal(str(row[1])), Decimal(str(paid))


async def summary(db: AsyncSession, seller_id: uuid.UUID) -> SettlementSummaryOut:
    sales, commission, paid = await _totals(db, seller_id)
    earned = sales - commission
    rows = (
        await db.execute(
            select(StoreOrder, Order.order_no, Delivery.delivered_at)
            .join(Order, Order.id == StoreOrder.order_id)
            .join(Delivery, (Delivery.order_id == StoreOrder.order_id) & (Delivery.status == DeliveryStatus.DELIVERED))
            .where(StoreOrder.seller_id == seller_id, StoreOrder.commission_amount.is_not(None))
            .order_by(Delivery.delivered_at.desc(), StoreOrder.id)
            .limit(RECENT)
        )
    ).all()
    payouts = (
        await db.scalars(select(SellerPayout).where(SellerPayout.seller_id == seller_id).order_by(SellerPayout.created_at.desc(), SellerPayout.id).limit(RECENT))
    ).all()
    return SettlementSummaryOut(
        total_sales=float(sales), total_commission=float(commission), total_earned=float(earned), total_paid=float(paid), due=float(earned - paid),
        recent_orders=[
            SettlementOrderOut(
                order_id=so.order_id, order_number=f"PD{order_no}", store_name=so.store_name, items_subtotal=float(so.items_subtotal),
                commission_rate=float(so.commission_rate), commission_amount=float(so.commission_amount),
                net=float(so.items_subtotal - so.commission_amount), delivered_at=delivered_at,
            )
            for so, order_no, delivered_at in rows
        ],
        recent_payouts=[SellerPayoutOut(id=p.id, amount=float(p.amount), note=p.note, created_at=p.created_at) for p in payouts],
    )


async def my_summary(db: AsyncSession, seller: Seller) -> SettlementSummaryOut:
    return await summary(db, seller.id)


async def admin_list(db: AsyncSession, include_settled: bool, limit: int, offset: int) -> list[AdminSettlementRowOut]:
    """Kis seller ko kitna dena baaki hai (sabse zyada pehle). Default: sirf jinka kuch baaki hai."""
    sold = (
        select(
            StoreOrder.seller_id.label("sid"),
            func.sum(StoreOrder.items_subtotal).label("sales"),
            func.sum(StoreOrder.commission_amount).label("comm"),
        )
        .where(StoreOrder.commission_amount.is_not(None))
        .group_by(StoreOrder.seller_id)
        .subquery()
    )
    pay = select(SellerPayout.seller_id.label("sid"), func.sum(SellerPayout.amount).label("p")).group_by(SellerPayout.seller_id).subquery()
    paid = func.coalesce(pay.c.p, 0)
    earned = sold.c.sales - sold.c.comm
    q = (
        select(Seller, User.phone, sold.c.sales, sold.c.comm, paid)
        .join(User, User.id == Seller.user_id)
        .join(sold, sold.c.sid == Seller.id)
        .outerjoin(pay, pay.c.sid == Seller.id)
        .order_by((earned - paid).desc(), Seller.id)
        .limit(limit)
        .offset(offset)
    )
    if not include_settled:
        q = q.where(earned - paid > 0)
    out = []
    for s, phone, sales, comm, pd in (await db.execute(q)).all():
        sales, comm, pd = Decimal(str(sales)), Decimal(str(comm)), Decimal(str(pd))
        out.append(
            AdminSettlementRowOut(
                seller_id=s.id, business_name=s.business_name, phone=phone, status=s.status, total_sales=float(sales),
                total_commission=float(comm), total_earned=float(sales - comm), total_paid=float(pd), due=float(sales - comm - pd),
            )
        )
    return out


async def admin_detail(db: AsyncSession, seller_id: uuid.UUID) -> SettlementSummaryOut:
    if await db.get(Seller, seller_id) is None:
        raise api_error(404, "SELLER_NOT_FOUND", "Seller nahi mila.")
    return await summary(db, seller_id)


async def record_payout(
    db: AsyncSession, admin: User, request: Request, seller_id: uuid.UUID, amount: Decimal, note: str | None
) -> SettlementSummaryOut:
    seller = await db.scalar(select(Seller).where(Seller.id == seller_id).with_for_update().execution_options(populate_existing=True))
    if seller is None:
        raise api_error(404, "SELLER_NOT_FOUND", "Seller nahi mila.")
    sales, commission, paid = await _totals(db, seller_id)
    earned = sales - commission
    problem = deposit_problem(earned, paid, amount)  # wahi niyam: paid kamai se zyada nahi, sudhaar paid se zyada nahi
    if problem == "EXCEEDS":
        raise api_error(409, "SETTLEMENT_EXCEEDS_DUE", "Itna paisa seller ka baaki nahi hai.")
    if problem == "BELOW_ZERO":
        raise api_error(409, "SETTLEMENT_CORRECTION_TOO_BIG", "Sudhaar ab tak diye hue paise se zyada nahi ho sakta.")
    db.add(SellerPayout(seller_id=seller_id, amount=amount, note=note, recorded_by=admin.id))
    if amount > 0:  # sudhaar (negative) par seller ko khabar nahi
        notification.add(db, seller.user_id, "SELLER_PAYOUT_RECEIVED", {"amount": f"{amount:.2f}"})
    write_audit(
        db, actor=admin, action="settlement.payout", target_type="seller", target_id=seller_id,
        old={"due": str(earned - paid)}, new={"due": str(earned - paid - amount), "amount": str(amount)}, reason=note, request=request,
    )
    await db.commit()
    return await summary(db, seller_id)