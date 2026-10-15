"""Commission ke seedhe hisaab (bina database ke, taaki alag se jaanch sako)."""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def rate_for_store_type(store_type: str | None, kirana_rate: Decimal, restaurant_rate: Decimal) -> Decimal:
    """Dukaan RESTAURANT hai to restaurant ka rate, warna kirana ka."""
    return Decimal(str(restaurant_rate if store_type == "RESTAURANT" else kirana_rate))


def commission_amount(items_subtotal, rate) -> Decimal:
    """Dukaan ki bikri x rate% (paise me, aadha paisa upar). Commission bikri se zyada kabhi nahi hota (rate <= 100)."""
    return (Decimal(str(items_subtotal)) * Decimal(str(rate)) / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)