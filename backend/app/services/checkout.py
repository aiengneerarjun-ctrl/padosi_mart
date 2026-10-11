"""Checkout preview: cart + address + delivery charge. Order abhi nahi banta (wo agle step me).

Delivery charge ke rules (owner ne tay kiye):
- Minimum order amount nahi hai: kitne ka bhi order ho sakta hai.
- Har order par ek delivery charge lagta hai (cart me kitni bhi dukaanein hon, ek order = ek charge).
- FREE_DELIVERY_FROM ya usse zyada ke saaman par delivery free.
"""
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import User
from app.schemas.checkout import CheckoutPreview
from app.services import cart as cart_service
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


async def preview(db: AsyncSession, user: User, address_id: uuid.UUID | None, lang: str) -> CheckoutPreview:
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
    return CheckoutPreview(
        address=address,
        stores=cart.stores,
        item_count=cart.item_count,
        items_subtotal=float(subtotal),
        delivery_fee=float(fee),
        free_delivery_from=float(FREE_DELIVERY_FROM),
        free_delivery_remaining=float(free_delivery_remaining(subtotal)),
        total=float(subtotal + fee),
        can_checkout=not blockers,
        blockers=blockers,
    )