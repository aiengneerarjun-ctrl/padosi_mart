"""Coupons.

Niyam (owner ne tay kiye):
- Jo coupon banata hai, wahi discount ka kharcha uthata hai (funded_by):
  * Super Admin banaye -> PLATFORM (Padosi): seller ko poora paisa milta hai, discount Padosi ke kharche me. Types: FLAT, PERCENT (max limit ke
    saath), FREE_DELIVERY. Optional: sirf pehle order par. Chahe to kisi ek seller ke saaman tak seedhe seller_id se bandh sakta hai.
  * Seller banaye -> SELLER: discount seller ke payout se kat'ta hai (store_orders.seller_discount) aur sirf uske apne saaman par lagta hai.
    Seller sirf FLAT / PERCENT bana sakta hai (free delivery nahi). Commission discount se pehle ki bikri par hi lagta hai.
- Discount sirf saaman par (FREE_DELIVERY me delivery charge par). Delivery partner ki kamai par koi asar nahi.
- Ek order par ek hi coupon. Customer ko kam se kam MIN_PAYABLE dena hoga.
- Limit: har customer kitni baar (per_user_limit) aur kul kitni baar (total_limit). Order cancel ho to coupon wapas (released_at).
- Seller ne items hataye to discount dobara nikalta hai: kabhi badhta nahi, min order na bache to 0 (customer ko notice + cancel ka mauka).
- Order place karte waqt coupon row lock hoti hai, isliye limit ke aakhri hisse par do customer ek saath nahi nikal sakte.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import localized, translate
from app.models import Coupon, CouponRedemption, Order, Seller, StoreOrder, User
from app.models.order import StoreOrderStatus
from app.models.seller import SellerStatus
from app.schemas.coupon import CouponAdminOut, CouponCreate, CouponOut, CouponPatch, SellerCouponCreate
from app.services import coupon_rules as rules
from app.services.audit import write_audit

INACTIVE = (StoreOrderStatus.REJECTED, StoreOrderStatus.CANCELLED)
NOT_A_REAL_ORDER = ("CANCELLED", "PAYMENT_FAILED")  # "pehla order" ginte waqt ye nahi ginte


@dataclass(frozen=True)
class Part:
    store_id: uuid.UUID
    seller_id: uuid.UUID
    subtotal: Decimal


@dataclass
class Quote:
    coupon: Coupon
    discount: Decimal
    shares: dict  # {store_id: seller ka hissa} (PLATFORM-funded me khali)


def normalize(code: str | None) -> str:
    return (code or "").strip().upper()


def _eligible(coupon: Coupon, parts: list[Part]) -> list[Part]:
    return [p for p in parts if coupon.seller_id is None or p.seller_id == coupon.seller_id]


async def _used(db: AsyncSession, coupon_id: uuid.UUID, user_id: uuid.UUID | None = None) -> int:
    q = select(func.count()).select_from(CouponRedemption).where(CouponRedemption.coupon_id == coupon_id, CouponRedemption.released_at.is_(None))
    if user_id is not None:
        q = q.where(CouponRedemption.user_id == user_id)
    return await db.scalar(q) or 0


async def _is_first_order(db: AsyncSession, user_id: uuid.UUID) -> bool:
    n = await db.scalar(select(func.count()).select_from(Order).where(Order.user_id == user_id, Order.status.not_in(NOT_A_REAL_ORDER)))
    return (n or 0) == 0


async def evaluate(
    db: AsyncSession, user: User, code: str, parts: list[Part], items_subtotal: Decimal, fee: Decimal, *, lock: bool = False
) -> tuple[Quote | None, str | None]:
    """(quote, None) ya (None, error_code). lock=True: order banate waqt (coupon row lock, limit sahi gine)."""
    q = select(Coupon).where(Coupon.code == normalize(code)).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    c = await db.scalar(q)
    if c is None:
        return None, "COUPON_NOT_FOUND"
    problem = rules.window_problem(c.is_active, c.starts_at, c.expires_at, datetime.now(timezone.utc))
    if problem:
        return None, problem
    mine = _eligible(c, parts)
    eligible = sum((p.subtotal for p in mine), Decimal("0"))
    if not mine or eligible <= 0:
        return None, "COUPON_NOT_APPLICABLE"
    if eligible < c.min_order_amount:
        return None, "COUPON_MIN_ORDER"
    if c.first_order_only and not await _is_first_order(db, user.id):
        return None, "COUPON_FIRST_ORDER_ONLY"
    if await _used(db, c.id, user.id) >= c.per_user_limit:
        return None, "COUPON_USER_LIMIT"
    if c.total_limit is not None and await _used(db, c.id) >= c.total_limit:
        return None, "COUPON_LIMIT_REACHED"
    discount = rules.compute_discount(c.discount_type, c.value, c.max_discount, eligible, items_subtotal, fee)
    if discount <= 0:
        return None, "COUPON_NO_DISCOUNT"  # jaise delivery pehle se free hai
    shares = rules.split_discount([(p.store_id, p.subtotal) for p in mine], discount) if c.funded_by == "SELLER" else {}
    return Quote(c, discount, shares), None


async def release(db: AsyncSession, order_id: uuid.UUID) -> None:
    """Order cancel / saare items hat gaye: coupon ki ginti se hata do (customer dobara use kar sakta hai)."""
    await db.execute(
        update(CouponRedemption)
        .where(CouponRedemption.order_id == order_id, CouponRedemption.released_at.is_(None))
        .values(released_at=func.now())
        .execution_options(synchronize_session=False)
    )


async def reprice(db: AsyncSession, order: Order) -> None:
    """Seller ne items hataye: discount aur seller ke hisse dobara, order.total set karo (COMMIT caller karta hai).
    Caller ne order.items_subtotal aur order.delivery_fee pehle set kiye hone chahiye. Koi dukaan na bache to sirf hisse 0 karta hai."""
    live = [so for so in order.store_orders if so.status not in INACTIVE]
    for so in order.store_orders:
        if so not in live:
            so.seller_discount = Decimal("0")
    if not live:
        return
    discount = Decimal("0")
    coupon = None
    if order.coupon_id:
        with db.no_autoflush:  # beech me adhoori (naye subtotal, purana seller_discount) halat DB me na jaye
            coupon = await db.get(Coupon, order.coupon_id)
        eligible = sum((so.items_subtotal for so in live if coupon.seller_id is None or so.seller_id == coupon.seller_id), Decimal("0"))
        if eligible > 0 and eligible >= coupon.min_order_amount:
            new = rules.compute_discount(coupon.discount_type, coupon.value, coupon.max_discount, eligible, order.items_subtotal, order.delivery_fee)
            discount = min(order.discount_amount, new)  # discount kabhi badhta nahi
    order.discount_amount = discount
    order.total = order.items_subtotal + order.delivery_fee - discount
    shares: dict = {}
    if coupon is not None and coupon.funded_by == "SELLER" and discount > 0:
        mine = [so for so in live if so.seller_id == coupon.seller_id]
        shares = rules.split_discount([(so.id, so.items_subtotal) for so in mine], discount)
    for so in live:
        so.seller_discount = shares.get(so.id, Decimal("0"))


# ---------------- Customer ----------------


async def list_for_customer(db: AsyncSession, user: User, limit: int, offset: int, lang: str) -> list[CouponOut]:
    now = datetime.now(timezone.utc)
    coupons = (
        await db.scalars(
            select(Coupon)
            .where(Coupon.is_active.is_(True), Coupon.is_public.is_(True), Coupon.starts_at <= now, Coupon.expires_at > now)
            .order_by(Coupon.created_at.desc(), Coupon.id).limit(limit).offset(offset)
        )
    ).all()
    ids = [c.id for c in coupons]
    mine: dict = {}
    total: dict = {}
    if ids:
        base = select(CouponRedemption.coupon_id, func.count()).where(CouponRedemption.coupon_id.in_(ids), CouponRedemption.released_at.is_(None))
        total = dict((await db.execute(base.group_by(CouponRedemption.coupon_id))).all())
        mine = dict((await db.execute(base.where(CouponRedemption.user_id == user.id).group_by(CouponRedemption.coupon_id))).all())
    first = await _is_first_order(db, user.id)
    out = []
    for c in coupons:
        reason = None
        if c.first_order_only and not first:
            reason = "COUPON_FIRST_ORDER_ONLY"
        elif mine.get(c.id, 0) >= c.per_user_limit:
            reason = "COUPON_USER_LIMIT"
        elif c.total_limit is not None and total.get(c.id, 0) >= c.total_limit:
            reason = "COUPON_LIMIT_REACHED"
        out.append(
            CouponOut(
                id=c.id, code=c.code, title=localized(c, lang, "title"), discount_type=c.discount_type, value=float(c.value),
                max_discount=float(c.max_discount) if c.max_discount is not None else None, min_order_amount=float(c.min_order_amount),
                first_order_only=c.first_order_only, seller_id=c.seller_id, expires_at=c.expires_at, usable=reason is None,
                unusable_reason=reason, unusable_message=translate(reason, lang) if reason else None,
            )
        )
    return out


# ---------------- Admin ----------------


async def _admin_out(db: AsyncSession, coupons: list[Coupon]) -> list[CouponAdminOut]:
    stats = {}
    if coupons:
        rows = await db.execute(
            select(CouponRedemption.coupon_id, func.count(), func.coalesce(func.sum(CouponRedemption.discount_amount), 0))
            .where(CouponRedemption.coupon_id.in_([c.id for c in coupons]), CouponRedemption.released_at.is_(None))
            .group_by(CouponRedemption.coupon_id)
        )
        stats = {cid: (n, amt) for cid, n, amt in rows.all()}
    return [
        CouponAdminOut(
            id=c.id, code=c.code, title=c.title, title_hi=c.title_hi, title_bho=c.title_bho, discount_type=c.discount_type,
            value=float(c.value), max_discount=float(c.max_discount) if c.max_discount is not None else None,
            min_order_amount=float(c.min_order_amount), funded_by=c.funded_by, seller_id=c.seller_id, first_order_only=c.first_order_only,
            is_public=c.is_public, per_user_limit=c.per_user_limit, total_limit=c.total_limit, starts_at=c.starts_at,
            expires_at=c.expires_at, is_active=c.is_active, used_count=stats.get(c.id, (0, 0))[0],
            total_discount_given=float(stats.get(c.id, (0, 0))[1]), created_at=c.created_at,
        )
        for c in coupons
    ]


async def _get(db: AsyncSession, coupon_id: uuid.UUID, *, lock: bool = False) -> Coupon:
    q = select(Coupon).where(Coupon.id == coupon_id).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    c = await db.scalar(q)
    if c is None:
        raise api_error(404, "COUPON_NOT_FOUND", "Coupon nahi mila.")
    return c


async def admin_list(db: AsyncSession, active: bool | None, limit: int, offset: int) -> list[CouponAdminOut]:
    q = select(Coupon)
    if active is not None:
        q = q.where(Coupon.is_active.is_(active))
    coupons = (await db.scalars(q.order_by(Coupon.created_at.desc(), Coupon.id).limit(limit).offset(offset))).all()
    return await _admin_out(db, list(coupons))


async def admin_get(db: AsyncSession, coupon_id: uuid.UUID) -> CouponAdminOut:
    return (await _admin_out(db, [await _get(db, coupon_id)]))[0]


MAX_ACTIVE_SELLER_COUPONS = 20  # ek seller ke ek saath chalne wale coupons


async def _create(db: AsyncSession, actor: User, request: Request, body: CouponCreate, action: str) -> CouponAdminOut:
    if body.seller_id is not None and await db.get(Seller, body.seller_id) is None:
        raise api_error(404, "SELLER_NOT_FOUND", "Seller nahi mila.")
    if await db.scalar(select(Coupon.id).where(Coupon.code == body.code)) is not None:
        raise api_error(409, "COUPON_CODE_EXISTS", "Ye coupon code pehle se hai.")
    now = datetime.now(timezone.utc)
    c = Coupon(
        id=uuid.uuid4(), code=body.code, title=body.title, title_hi=body.title_hi, title_bho=body.title_bho,
        discount_type=body.discount_type, value=body.value, max_discount=body.max_discount, min_order_amount=body.min_order_amount,
        funded_by=body.funded_by, seller_id=body.seller_id, first_order_only=body.first_order_only, is_public=body.is_public,
        per_user_limit=body.per_user_limit, total_limit=body.total_limit, starts_at=body.starts_at or now,
        expires_at=body.expires_at, created_by=actor.id,
    )
    if c.expires_at <= c.starts_at:
        raise api_error(422, "COUPON_DATES_INVALID", "Coupon ki khatam hone ki tareekh shuru hone ke baad ki honi chahiye.")
    db.add(c)
    write_audit(
        db, actor=actor, action=action, target_type="coupon", target_id=c.id,
        new={"code": c.code, "type": c.discount_type, "value": str(c.value), "funded_by": c.funded_by}, request=request,
    )
    try:
        await db.commit()
    except IntegrityError:  # do log ek saath wahi code bana rahe the
        await db.rollback()
        raise api_error(409, "COUPON_CODE_EXISTS", "Ye coupon code pehle se hai.")
    return await admin_get(db, c.id)


async def admin_create(db: AsyncSession, admin: User, request: Request, body: CouponCreate) -> CouponAdminOut:
    if body.funded_by != "PLATFORM":  # jo banata hai wahi kharcha uthata hai: admin ka coupon Padosi ka kharcha hai
        raise api_error(422, "COUPON_ADMIN_PLATFORM_ONLY", "Admin ka coupon Padosi ke kharche par hota hai.")
    return await _create(db, admin, request, body, "coupon.create")


async def _patch(
    db: AsyncSession, actor: User, request: Request, coupon_id: uuid.UUID, body: CouponPatch, action: str, seller: Seller | None = None
) -> CouponAdminOut:
    c = await _get(db, coupon_id, lock=True)
    if seller is not None and (c.funded_by != "SELLER" or c.seller_id != seller.id):  # doosre seller ka / admin ka coupon: 404
        await db.rollback()
        raise api_error(404, "COUPON_NOT_FOUND", "Coupon nahi mila.")
    changes = {f: getattr(body, f) for f in body.model_fields_set - {"reason"}}
    old = {f: str(getattr(c, f)) for f in changes}
    for f, v in changes.items():
        setattr(c, f, v)
    if c.expires_at <= c.starts_at:
        await db.rollback()
        raise api_error(422, "COUPON_DATES_INVALID", "Coupon ki khatam hone ki tareekh shuru hone ke baad ki honi chahiye.")
    if c.total_limit is not None and c.total_limit < await _used(db, c.id):
        await db.rollback()
        raise api_error(409, "COUPON_LIMIT_TOO_LOW", "Limit ab tak ke istemal se kam nahi ho sakti.")
    write_audit(
        db, actor=actor, action=action, target_type="coupon", target_id=c.id, old=old,
        new={f: str(v) for f, v in changes.items()}, reason=body.reason, request=request,
    )
    await db.commit()
    return await admin_get(db, c.id)


async def admin_patch(db: AsyncSession, admin: User, request: Request, coupon_id: uuid.UUID, body: CouponPatch) -> CouponAdminOut:
    return await _patch(db, admin, request, coupon_id, body, "coupon.update")


# ---------------- Seller (apna coupon) ----------------


def _require_active_seller(seller: Seller) -> None:
    if seller.status != SellerStatus.ACTIVE:
        raise api_error(403, "SELLER_NOT_ACTIVE", "Aapka seller account abhi active nahi hai.")


async def seller_create(db: AsyncSession, user: User, seller: Seller, request: Request, body: SellerCouponCreate) -> CouponAdminOut:
    _require_active_seller(seller)
    await db.scalar(select(Seller.id).where(Seller.id == seller.id).with_for_update())  # ek seller ke do coupon ek saath bane to gintee sahi rahe
    running = await db.scalar(
        select(func.count()).select_from(Coupon).where(
            Coupon.seller_id == seller.id, Coupon.funded_by == "SELLER", Coupon.is_active.is_(True), Coupon.expires_at > func.now()
        )
    )
    if (running or 0) >= MAX_ACTIVE_SELLER_COUPONS:
        await db.rollback()
        raise api_error(409, "COUPON_SELLER_LIMIT", "Itne coupons ek saath chalu nahi ho sakte.")
    full = CouponCreate(**body.model_dump(), funded_by="SELLER", seller_id=seller.id)
    return await _create(db, user, request, full, "coupon.seller_create")


async def seller_list(db: AsyncSession, seller: Seller, active: bool | None, limit: int, offset: int) -> list[CouponAdminOut]:
    q = select(Coupon).where(Coupon.seller_id == seller.id, Coupon.funded_by == "SELLER")
    if active is not None:
        q = q.where(Coupon.is_active.is_(active))
    coupons = (await db.scalars(q.order_by(Coupon.created_at.desc(), Coupon.id).limit(limit).offset(offset))).all()
    return await _admin_out(db, list(coupons))


async def seller_get(db: AsyncSession, seller: Seller, coupon_id: uuid.UUID) -> CouponAdminOut:
    c = await _get(db, coupon_id)
    if c.funded_by != "SELLER" or c.seller_id != seller.id:
        raise api_error(404, "COUPON_NOT_FOUND", "Coupon nahi mila.")
    return (await _admin_out(db, [c]))[0]


async def seller_patch(db: AsyncSession, user: User, seller: Seller, request: Request, coupon_id: uuid.UUID, body: CouponPatch) -> CouponAdminOut:
    _require_active_seller(seller)
    return await _patch(db, user, request, coupon_id, body, "coupon.seller_update", seller=seller)
