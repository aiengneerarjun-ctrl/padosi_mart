"""Coupon ke seedhe hisaab (bina database ke, taaki alag se jaanch sako). Paisa hamesha Decimal."""
from datetime import datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_PAYABLE = Decimal("1.00")  # coupon ke baad bhi customer ko kam se kam itna dena hoga (0 ka online payment nahi ho sakta)
FLAT, PERCENT, FREE_DELIVERY = "FLAT", "PERCENT", "FREE_DELIVERY"


def window_problem(is_active: bool, starts_at: datetime, expires_at: datetime, now: datetime) -> str | None:
    if not is_active:
        return "COUPON_INACTIVE"
    if now < starts_at:
        return "COUPON_NOT_STARTED"
    if now >= expires_at:
        return "COUPON_EXPIRED"
    return None


def compute_discount(discount_type: str, value, max_discount, eligible_subtotal, items_subtotal, delivery_fee) -> Decimal:
    """Discount kitna. eligible_subtotal = jin dukaanon par coupon lagta hai unka saaman; items_subtotal = poore order ka saaman."""
    eligible, items, fee = Decimal(str(eligible_subtotal)), Decimal(str(items_subtotal)), Decimal(str(delivery_fee))
    if discount_type == FLAT:
        d = min(Decimal(str(value)), eligible)
    elif discount_type == PERCENT:
        d = (eligible * Decimal(str(value)) / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
        if max_discount is not None:
            d = min(d, Decimal(str(max_discount)))
    elif discount_type == FREE_DELIVERY:
        d = fee
    else:
        d = Decimal("0")
    d = min(d, items + fee - MIN_PAYABLE)  # customer kam se kam MIN_PAYABLE de
    return max(d, Decimal("0")).quantize(CENT)


def split_discount(parts: list[tuple[object, Decimal]], discount: Decimal) -> dict:
    """Seller-funded discount ko dukaan-hisson me bantna (unke saaman ke hisaab se). Jod hamesha discount ke barabar,
    aur kisi hisse ka share uske saaman se zyada nahi. parts = [(key, subtotal)]."""
    discount = Decimal(str(discount))
    out = {k: Decimal("0.00") for k, _ in parts}
    total = sum((Decimal(str(s)) for _, s in parts), Decimal("0"))
    if discount <= 0 or total <= 0:
        return out
    discount = min(discount, total)
    for k, s in parts:
        out[k] = (discount * Decimal(str(s)) / total).quantize(CENT, rounding=ROUND_DOWN)
    left = int((discount - sum(out.values())) / CENT)  # bache hue paise, ek-ek karke sabse bade hisse se shuru
    order = sorted(parts, key=lambda p: Decimal(str(p[1])), reverse=True)
    while left > 0:
        moved = False
        for k, s in order:
            if left > 0 and out[k] + CENT <= Decimal(str(s)):
                out[k] += CENT
                left -= 1
                moved = True
        if not moved:
            break
    return out
