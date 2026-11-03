"""Seller ka hisaab: product commission aur manual settlement.

- Delivery poori hote hi fulfilled order items par product approval snapshot se commission fix hota hai.
  Percentage item sale par aur fixed rate selected unit quantity se lagta hai. Fail / cancel / reject hue hisse par kuch nahi.
- Seller ko dena baaki = kul bikri - kul commission - admin ne jitna diya. Admin seller ko paisa deta hai aur "paid" entry likhta hai
  (seller_payouts, badalta nahi). Paid kabhi kamai se zyada nahi; galti hui to negative sudhaar + note.
- COD cash ka hisaab alag hai (partner admin ko cash jama karta hai); seller ka paisa us cash se nahi kategta.
Lock: seller row (payout likhte waqt), taaki do admin ek saath galat hisaab na likh dein.
"""
import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Delivery, Order, OrderItem, OrderItemCommissionSnapshot, OrderItemRemoval, Seller, SellerPayout, StoreOrder, User
from app.models.delivery import DeliveryStatus
from app.models.order import StoreOrderStatus
from app.schemas.settlement import (
    AdminSettlementRowOut, SellerPayoutOut, SettlementCommissionItemOut, SettlementOrderOut, SettlementSummaryOut,
)
from app.services import notification
from app.services.audit import write_audit
from app.services.delivery_rules import deposit_problem
from app.services.settlement_rules import product_commission

INACTIVE = (StoreOrderStatus.REJECTED, StoreOrderStatus.CANCELLED)
RECENT = 20


async def _commission_rules(db: AsyncSession, items: list[OrderItem]) -> dict[uuid.UUID, OrderItemCommissionSnapshot]:
    if not items:
        return {}
    return {
        row.order_item_id: row
        for row in await db.scalars(
            select(OrderItemCommissionSnapshot).where(OrderItemCommissionSnapshot.order_item_id.in_({i.id for i in items}))
        )
    }


def _rule_for(item: OrderItem, snapshots: dict[uuid.UUID, OrderItemCommissionSnapshot]):
    rule = snapshots.get(item.id)
    return rule or item


async def apply_commission(db: AsyncSession, order: Order) -> None:
    """Delivered item quantities par product approval ke waqt snapshot hua commission fix karo."""
    live = [so for so in order.store_orders if so.status not in INACTIVE and so.commission_amount is None]
    if not live:
        return
    for so in live:
        items = list(await db.scalars(select(OrderItem).where(OrderItem.store_order_id == so.id)))
        removals = {
            r.order_item_id: r for r in await db.scalars(
                select(OrderItemRemoval).where(OrderItemRemoval.store_order_id == so.id)
            )
        }
        snapshots = await _commission_rules(db, items)
        total_commission = Decimal("0")
        for item in items:
            removed = removals.get(item.id)
            # Partial removal creates a separate kept-item row; do not count its quantity twice.
            fulfilled_qty = (0 if removed.kept_item_id else (removed.kept_quantity or 0)) if removed else item.quantity
            rule = _rule_for(item, snapshots)
            total_commission += product_commission(
                item.unit_price, fulfilled_qty, rule.commission_mode, rule.commission_value, rule.commission_unit_quantity
            )
        so.commission_amount = total_commission.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Purane clients ke commission_rate field ko effective blended rate ke roop me bhejo.
        so.commission_rate = (
            (so.commission_amount * Decimal("100") / so.items_subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if so.items_subtotal else Decimal("0")
        )


async def _totals(db: AsyncSession, seller_id: uuid.UUID) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """(kul bikri, kul commission, kul paid, seller-funded coupon me seller ka kul hissa)"""
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(StoreOrder.items_subtotal), 0), func.coalesce(func.sum(StoreOrder.commission_amount), 0),
                func.coalesce(func.sum(StoreOrder.seller_discount), 0),
            )
            .where(StoreOrder.seller_id == seller_id, StoreOrder.commission_amount.is_not(None))
        )
    ).one()
    paid = await db.scalar(select(func.coalesce(func.sum(SellerPayout.amount), 0)).where(SellerPayout.seller_id == seller_id))
    return Decimal(str(row[0])), Decimal(str(row[1])), Decimal(str(paid)), Decimal(str(row[2]))


async def summary(db: AsyncSession, seller_id: uuid.UUID) -> SettlementSummaryOut:
    sales, commission, paid, seller_discount = await _totals(db, seller_id)
    earned = sales - commission - seller_discount
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
    recent_orders = []
    for so, order_no, delivered_at in rows:
        items = list(so.items)
        snapshots = await _commission_rules(db, items)
        removals = {
            r.order_item_id: r for r in await db.scalars(
                select(OrderItemRemoval).where(OrderItemRemoval.store_order_id == so.id)
            )
        }
        details = []
        for item in items:
            removed = removals.get(item.id)
            qty = (0 if removed.kept_item_id else (removed.kept_quantity or 0)) if removed else item.quantity
            rule = _rule_for(item, snapshots)
            amount = product_commission(item.unit_price, qty, rule.commission_mode, rule.commission_value, rule.commission_unit_quantity)
            if amount > 0:
                details.append(SettlementCommissionItemOut(
                    name=item.name, selling_unit=item.selling_unit, quantity=qty,
                    commission_mode=rule.commission_mode, commission_unit=rule.commission_unit,
                    commission_value=float(rule.commission_value), commission_unit_quantity=float(rule.commission_unit_quantity),
                    commission_amount=float(amount),
                ))
        recent_orders.append(SettlementOrderOut(
            order_id=so.order_id, order_number=f"PD{order_no}", store_name=so.store_name, items_subtotal=float(so.items_subtotal),
            commission_rate=float(so.commission_rate or 0), commission_amount=float(so.commission_amount),
            seller_discount=float(so.seller_discount), net=float(so.items_subtotal - so.commission_amount - so.seller_discount),
            delivered_at=delivered_at, commission_items=details,
        ))
    return SettlementSummaryOut(
        total_sales=float(sales), total_commission=float(commission), total_seller_discount=float(seller_discount),
        total_earned=float(earned), total_paid=float(paid), due=float(earned - paid),
        recent_orders=recent_orders,
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
            func.sum(StoreOrder.seller_discount).label("disc"),
        )
        .where(StoreOrder.commission_amount.is_not(None))
        .group_by(StoreOrder.seller_id)
        .subquery()
    )
    pay = select(SellerPayout.seller_id.label("sid"), func.sum(SellerPayout.amount).label("p")).group_by(SellerPayout.seller_id).subquery()
    paid = func.coalesce(pay.c.p, 0)
    earned = sold.c.sales - sold.c.comm - sold.c.disc
    q = (
        select(Seller, User.phone, sold.c.sales, sold.c.comm, paid, sold.c.disc)
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
    for s, phone, sales, comm, pd, disc in (await db.execute(q)).all():
        sales, comm, pd, disc = Decimal(str(sales)), Decimal(str(comm)), Decimal(str(pd)), Decimal(str(disc))
        out.append(
            AdminSettlementRowOut(
                seller_id=s.id, business_name=s.business_name, phone=phone, status=s.status, total_sales=float(sales),
                total_commission=float(comm), total_seller_discount=float(disc), total_earned=float(sales - comm - disc),
                total_paid=float(pd), due=float(sales - comm - disc - pd),
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
    sales, commission, paid, seller_discount = await _totals(db, seller_id)
    earned = sales - commission - seller_discount
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
