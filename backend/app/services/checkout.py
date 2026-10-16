"""Checkout preview: cart + address + delivery charge + coupon. Order abhi nahi banta (wo order service me).

Delivery charge ke rules (owner ne tay kiye):
- Minimum order amount nahi hai: kitne ka bhi order ho sakta hai.
- Har order par ek delivery charge lagta hai (cart me kitni bhi dukaanein hon, ek order = ek charge).
- FREE_DELIVERY_FROM ya usse zyada ke saaman par delivery free.
Coupon (services/coupon.py): discount total me se kat'ta hai. Coupon na chale to preview band nahi hota, bas coupon_error batata hai.
"""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import localized, translate
from app.models import Store, User
from app.schemas.checkout import CheckoutPreview
from app.schemas.coupon import CouponBrief
from app.services import cart as cart_service
from app.services import coupon as coupon_service
from app.services import customer as customer_service

DELIVERY_FEE = Decimal("30")  # <-- delivery charge yahan badlo
FREE_DELIVERY_FROM = Decimal("799")  # <-- itne ya zyada ke saaman par free


def delivery_fee_for(items_subtotal: Decimal) -> Decimal:
    """Saaman ke total par kitna delivery charge."""
    if items_subtotal <= 0 or items_subtotal >= FREE_DELIVERY_FROM:
        return Decimal("0")
    return DELIVERY_FEE


def free_delivery_remaining(items_subtotal: Decimal) -> Decimal:
    """Free delivery ke liye aur kitna jodna hai."""
    return max(FREE_DELIVERY_FROM - items_subtotal, Decimal("0"))


async def preview(db: AsyncSession, user: User, address_id: uuid.UUID | None, lang: str, coupon_code: str | None = None) -> CheckoutPreview:
    if address_id is not None:
        address = await customer_service._get_own(db, user, address_id)  # doosre ka address: 404
    else:
        addresses = await customer_service.list_addresses(db, user)  # default sabse pehle aata hai
        if not addresses:
            raise api_error(409, "ADDRESS_REQUIRED", "Pehle delivery address jodo.")
        address = addresses[0]

    # Location address se aati hai: eligibility, doori aur delivery radius usi se check hote hain
    cart = await cart_service.build_cart(db, user, float(address.latitude), float(address.longitude), lang)

    blockers: list[str] = []
    if not cart.stores:
        blockers.append("CART_EMPTY")
    elif cart.has_problems:
        blockers.append("ITEM_UNAVAILABLE")  # customer ko wo item hatane padenge
    elif cart.item_count == 0:
        blockers.append("CART_EMPTY")

    subtotal = Decimal(str(cart.subtotal))
    fee = delivery_fee_for(subtotal)

    discount, brief, coupon_error = Decimal("0"), None, None
    if coupon_code and coupon_code.strip() and cart.stores:
        seller_of = dict((await db.execute(select(Store.id, Store.seller_id).where(Store.id.in_({g.store_id for g in cart.stores})))).all())
        parts = [coupon_service.Part(g.store_id, seller_of[g.store_id], Decimal(str(g.subtotal))) for g in cart.stores]
        quote, coupon_error = await coupon_service.evaluate(db, user, coupon_code, parts, subtotal, fee)
        if quote is not None:
            discount = quote.discount
            brief = CouponBrief(code=quote.coupon.code, title=localized(quote.coupon, lang, "title"), discount_type=quote.coupon.discount_type)

    return CheckoutPreview(
        address=address,
        stores=cart.stores,
        item_count=cart.item_count,
        items_subtotal=float(subtotal),
        delivery_fee=float(fee),
        free_delivery_from=float(FREE_DELIVERY_FROM),
        free_delivery_remaining=float(free_delivery_remaining(subtotal)),
        discount_amount=float(discount),
        coupon=brief,
        coupon_error=coupon_error,
        coupon_message=translate(coupon_error, lang) if coupon_error else None,
        total=float(subtotal + fee - discount),
        can_checkout=not blockers,
        blockers=blockers,
    )
