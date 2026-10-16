"""Reviews: delivery ke baad customer dukaan ka aur delivery partner ka review deta hai.

Niyam (owner ne tay kiye):
- Sirf DELIVERED order par, delivery ke 7 din tak (REVIEW_WINDOW_DAYS). Customer apne order par hi.
- Dukaan: order ke har dukaan-hisse (jo reject / cancel nahi hua) ka ek review. Delivery partner: us delivery ka ek review.
  Ek hi cheez ka dobara review nahi (DB unique index se pakka hota hai). Review badalta / hatta nahi.
- 1 se 5 star + chhota comment (optional). Customer ka sirf pehla naam dikhta hai; partner ko customer ka naam nahi dikhta.
- Admin gandi / jhooti review chhupa sakta hai (karan zaroori, audit log). Chhupa hua review kisi ko nahi dikhta aur average me nahi ginta.
- Average: star ki ginti (rating_summaries) se; review aur ginti ek hi transaction me badalte hain.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import translate
from app.models import Delivery, DeliveryPartner, Order, RatingSummary, Review, Seller, Store, StoreOrder, User
from app.models.delivery import DeliveryStatus
from app.models.order import OrderStatus, StoreOrderStatus
from app.schemas.review import (
    AdminReviewOut, PartnerReviewOut, PartnerReviewsOut, PublicReviewOut, RatingSummaryOut, ReviewableOut, ReviewCreate, ReviewOut,
    ReviewTargetOut, SellerReviewOut, SellerReviewsOut, StoreReviewsOut,
)
from app.services.audit import write_audit

REVIEW_WINDOW_DAYS = 7
STORE, PARTNER = "STORE", "PARTNER"
INACTIVE = (StoreOrderStatus.REJECTED, StoreOrderStatus.CANCELLED)


# ---------- seedhe hisaab (bina database ke) ----------

def summarize(stars: dict[int, int]) -> RatingSummaryOut:
    count = sum(stars.get(i, 0) for i in range(1, 6))
    avg = None
    if count:
        avg = float((Decimal(sum(i * stars.get(i, 0) for i in range(1, 6))) / Decimal(count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return RatingSummaryOut(average=avg, count=count, stars={i: stars.get(i, 0) for i in range(1, 6)})


def first_name(name: str | None, lang: str) -> str:
    """Customer ka sirf pehla shabd; naam na ho to "Customer" (uski bhasha me)."""
    word = (name or "").strip().split(" ")[0][:30]
    return word or translate("REVIEWER_ANONYMOUS", lang)


def review_deadline(delivered_at: datetime) -> datetime:
    return delivered_at + timedelta(days=REVIEW_WINDOW_DAYS)


# ---------- rating_summaries ----------

async def _bump(db: AsyncSession, target_type: str, target_id: uuid.UUID, rating: int, delta: int) -> None:
    """Star ki ginti me +1 / -1 (atomic). Row na ho to banti hai."""
    col = f"star{rating}"
    stmt = pg_insert(RatingSummary).values(target_type=target_type, target_id=target_id, **{col: max(delta, 0)})
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=[RatingSummary.target_type, RatingSummary.target_id],
            set_={col: getattr(RatingSummary, col) + delta},
        )
    )


async def _stars(db: AsyncSession, target_type: str, target_ids: list[uuid.UUID]) -> dict[int, int]:
    if not target_ids:
        return {}
    cols = [func.coalesce(func.sum(getattr(RatingSummary, f"star{i}")), 0) for i in range(1, 6)]
    row = (await db.execute(select(*cols).where(RatingSummary.target_type == target_type, RatingSummary.target_id.in_(target_ids)))).one()
    return {i: int(row[i - 1]) for i in range(1, 6)}


# ---------- Customer ----------

async def _my_delivered_order(db: AsyncSession, user: User, order_id: uuid.UUID) -> tuple[Order, Delivery | None]:
    order = await db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id))
    if order is None:  # doosre ka order bhi 404
        raise api_error(404, "ORDER_NOT_FOUND", "Order nahi mila.")
    delivery = await db.scalar(select(Delivery).where(Delivery.order_id == order.id, Delivery.status == DeliveryStatus.DELIVERED))
    return order, delivery


def _window_problem(order: Order, delivery: Delivery | None, now: datetime) -> tuple[str | None, datetime | None]:
    if order.status != OrderStatus.DELIVERED or delivery is None or delivery.delivered_at is None:
        return "REVIEW_ORDER_NOT_DELIVERED", None
    until = review_deadline(delivery.delivered_at)
    return ("REVIEW_WINDOW_OVER" if now >= until else None), until


async def _targets(db: AsyncSession, order: Order, delivery: Delivery | None) -> list[tuple[str, uuid.UUID | None, str, uuid.UUID | None]]:
    """[(target, store_id, naam, seller_id)] — review diye ja sakne wali cheezein."""
    out = [(STORE, so.store_id, so.store_name, so.seller_id) for so in order.store_orders if so.status not in INACTIVE]
    if delivery is not None:
        full_name = await db.scalar(select(DeliveryPartner.full_name).where(DeliveryPartner.id == delivery.partner_id))
        out.append((PARTNER, None, (full_name or "").strip().split(" ")[0], None))
    return out


async def reviewable(db: AsyncSession, user: User, order_id: uuid.UUID, lang: str) -> ReviewableOut:
    order, delivery = await _my_delivered_order(db, user, order_id)
    problem, until = _window_problem(order, delivery, datetime.now(timezone.utc))
    done = {(r.target_type, r.store_id): r.id for r in await db.scalars(select(Review).where(Review.order_id == order.id, Review.user_id == user.id))}
    targets = []
    if order.status == OrderStatus.DELIVERED:
        for target, store_id, name, _ in await _targets(db, order, delivery):
            rid = done.get((target, store_id))
            targets.append(ReviewTargetOut(target=target, store_id=store_id, name=name, reviewed=rid is not None, review_id=rid))
    return ReviewableOut(
        order_id=order.id, can_review=problem is None, reason=problem, message=translate(problem, lang) if problem else None,
        review_until=until, targets=targets,
    )


async def create(db: AsyncSession, user: User, body: ReviewCreate, lang: str) -> ReviewOut:
    order, delivery = await _my_delivered_order(db, user, body.order_id)
    problem, _ = _window_problem(order, delivery, datetime.now(timezone.utc))
    if problem:
        raise api_error(409, problem, "Abhi review nahi de sakte.")

    match = [t for t in await _targets(db, order, delivery) if t[0] == body.target and t[1] == body.store_id]
    if not match:
        raise api_error(404, "REVIEW_TARGET_NOT_FOUND", "Is order me iska review dene ko kuch nahi hai.")
    _, store_id, name, seller_id = match[0]

    review = Review(
        id=uuid.uuid4(), order_id=order.id, user_id=user.id, target_type=body.target, store_id=store_id, seller_id=seller_id,
        partner_id=delivery.partner_id if body.target == PARTNER else None, rating=body.rating, comment=body.comment,
    )
    db.add(review)
    try:
        await db.flush()  # duplicate ho to yahin unique index pakadta hai (do request ek saath bhi)
    except IntegrityError:
        await db.rollback()
        raise api_error(409, "REVIEW_ALREADY_EXISTS", "Aap iska review de chuke hain.")
    await _bump(db, body.target, store_id if body.target == STORE else delivery.partner_id, body.rating, +1)
    await db.commit()
    return ReviewOut(
        id=review.id, order_id=order.id, order_number=order.order_number, target=body.target, store_id=store_id, name=name,
        rating=body.rating, comment=body.comment, is_hidden=False, created_at=review.created_at,
    )


async def my_reviews(db: AsyncSession, user: User, limit: int, offset: int) -> list[ReviewOut]:
    rows = (
        await db.execute(
            select(Review, Order.order_no, Store.name, DeliveryPartner.full_name)
            .join(Order, Order.id == Review.order_id)
            .outerjoin(Store, Store.id == Review.store_id)
            .outerjoin(DeliveryPartner, DeliveryPartner.id == Review.partner_id)
            .where(Review.user_id == user.id)
            .order_by(Review.created_at.desc(), Review.id).limit(limit).offset(offset)
        )
    ).all()
    return [
        ReviewOut(
            id=r.id, order_id=r.order_id, order_number=f"PD{no}", target=r.target_type, store_id=r.store_id,
            name=store_name or (partner_name or "").strip().split(" ")[0], rating=r.rating, comment=r.comment,
            is_hidden=r.status == "HIDDEN", created_at=r.created_at,
        )
        for r, no, store_name, partner_name in rows
    ]


# ---------- Dukaan ke reviews (customer ko dikhte hain) ----------

async def store_reviews(db: AsyncSession, store_id: uuid.UUID, limit: int, offset: int, lang: str) -> StoreReviewsOut:
    if await db.scalar(select(Store.id).where(Store.id == store_id)) is None:
        raise api_error(404, "STORE_NOT_FOUND", "Dukaan nahi mili.")
    rows = (
        await db.execute(
            select(Review, User.name)
            .join(User, User.id == Review.user_id)
            .where(Review.store_id == store_id, Review.target_type == STORE, Review.status == "VISIBLE")
            .order_by(Review.created_at.desc(), Review.id).limit(limit).offset(offset)
        )
    ).all()
    return StoreReviewsOut(
        summary=summarize(await _stars(db, STORE, [store_id])),
        reviews=[PublicReviewOut(rating=r.rating, comment=r.comment, reviewer_name=first_name(n, lang), created_at=r.created_at) for r, n in rows],
    )


# ---------- Seller ----------

async def seller_reviews(
    db: AsyncSession, seller: Seller, store_id: uuid.UUID | None, max_rating: int | None, limit: int, offset: int, lang: str
) -> SellerReviewsOut:
    own = list((await db.scalars(select(Store.id).where(Store.seller_id == seller.id))).all())
    if store_id is not None and store_id not in own:  # doosre ki dukaan: 404
        raise api_error(404, "STORE_NOT_FOUND", "Dukaan nahi mili.")
    ids = [store_id] if store_id else own
    q = (
        select(Review, User.name, Store.name, Order.order_no)
        .join(User, User.id == Review.user_id).join(Store, Store.id == Review.store_id).join(Order, Order.id == Review.order_id)
        .where(Review.seller_id == seller.id, Review.target_type == STORE, Review.status == "VISIBLE")
    )
    if store_id:
        q = q.where(Review.store_id == store_id)
    if max_rating:
        q = q.where(Review.rating <= max_rating)
    rows = (await db.execute(q.order_by(Review.created_at.desc(), Review.id).limit(limit).offset(offset))).all()
    return SellerReviewsOut(
        summary=summarize(await _stars(db, STORE, ids)),
        reviews=[
            SellerReviewOut(
                id=r.id, rating=r.rating, comment=r.comment, reviewer_name=first_name(n, lang), created_at=r.created_at,
                store_id=r.store_id, store_name=sn, order_number=f"PD{no}",
            )
            for r, n, sn, no in rows
        ],
    )


# ---------- Delivery partner ----------

async def partner_reviews(db: AsyncSession, user: User, limit: int, offset: int) -> PartnerReviewsOut:
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == user.id))
    if partner is None:
        raise api_error(403, "NOT_A_PARTNER", "Pehle delivery partner ke liye apply karo.")
    rows = (
        await db.execute(
            select(Review, Order.order_no).join(Order, Order.id == Review.order_id)
            .where(Review.partner_id == partner.id, Review.target_type == PARTNER, Review.status == "VISIBLE")
            .order_by(Review.created_at.desc(), Review.id).limit(limit).offset(offset)
        )
    ).all()
    return PartnerReviewsOut(
        summary=summarize(await _stars(db, PARTNER, [partner.id])),
        reviews=[PartnerReviewOut(rating=r.rating, comment=r.comment, order_number=f"PD{no}", created_at=r.created_at) for r, no in rows],
    )


# ---------- Admin ----------

def _admin_row(r: Review, order_no: int, store_name: str | None, partner_name: str | None, user_name: str | None) -> AdminReviewOut:
    return AdminReviewOut(
        id=r.id, order_id=r.order_id, order_number=f"PD{order_no}", target=r.target_type, store_id=r.store_id, store_name=store_name,
        partner_id=r.partner_id, partner_name=partner_name, user_id=r.user_id, reviewer_name=user_name, rating=r.rating, comment=r.comment,
        status=r.status, hidden_reason=r.hidden_reason, hidden_at=r.hidden_at, created_at=r.created_at,
    )


async def admin_list(
    db: AsyncSession, status: str | None, target: str | None, max_rating: int | None, limit: int, offset: int
) -> list[AdminReviewOut]:
    q = (
        select(Review, Order.order_no, Store.name, DeliveryPartner.full_name, User.name)
        .join(Order, Order.id == Review.order_id).join(User, User.id == Review.user_id)
        .outerjoin(Store, Store.id == Review.store_id).outerjoin(DeliveryPartner, DeliveryPartner.id == Review.partner_id)
    )
    if status:
        q = q.where(Review.status == status)
    if target:
        q = q.where(Review.target_type == target)
    if max_rating:
        q = q.where(Review.rating <= max_rating)
    rows = (await db.execute(q.order_by(Review.created_at.desc(), Review.id).limit(limit).offset(offset))).all()
    return [_admin_row(r, no, sn, pn, un) for r, no, sn, pn, un in rows]


async def _set_hidden(db: AsyncSession, admin: User, request: Request, review_id: uuid.UUID, hide: bool, reason: str | None) -> AdminReviewOut:
    review = await db.scalar(select(Review).where(Review.id == review_id).with_for_update().execution_options(populate_existing=True))
    if review is None:
        await db.rollback()
        raise api_error(404, "REVIEW_NOT_FOUND", "Review nahi mila.")
    want = "HIDDEN" if hide else "VISIBLE"
    if review.status != want:  # pehle se wahi halat ho to kuch nahi badalta (dobara bhejna theek hai)
        review.status = want
        review.hidden_reason = reason if hide else None
        review.hidden_by = admin.id if hide else None
        review.hidden_at = datetime.now(timezone.utc) if hide else None
        target_id = review.store_id if review.target_type == STORE else review.partner_id
        await _bump(db, review.target_type, target_id, review.rating, -1 if hide else +1)
        write_audit(
            db, actor=admin, action="review.hide" if hide else "review.unhide", target_type="review", target_id=review.id,
            old={"status": "VISIBLE" if hide else "HIDDEN"}, new={"status": want}, reason=reason, request=request,
        )
    await db.commit()
    return await admin_list_one(db, review_id)


async def admin_list_one(db: AsyncSession, review_id: uuid.UUID) -> AdminReviewOut:
    q = (
        select(Review, Order.order_no, Store.name, DeliveryPartner.full_name, User.name)
        .join(Order, Order.id == Review.order_id).join(User, User.id == Review.user_id)
        .outerjoin(Store, Store.id == Review.store_id).outerjoin(DeliveryPartner, DeliveryPartner.id == Review.partner_id)
        .where(Review.id == review_id).execution_options(populate_existing=True)
    )
    r, no, sn, pn, un = (await db.execute(q)).one()
    return _admin_row(r, no, sn, pn, un)


async def hide(db: AsyncSession, admin: User, request: Request, review_id: uuid.UUID, reason: str) -> AdminReviewOut:
    return await _set_hidden(db, admin, request, review_id, True, reason)


async def unhide(db: AsyncSession, admin: User, request: Request, review_id: uuid.UUID) -> AdminReviewOut:
    return await _set_hidden(db, admin, request, review_id, False, None)
