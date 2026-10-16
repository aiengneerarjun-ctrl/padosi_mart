from pydantic import BaseModel

from app.schemas.cart import CartStoreGroup
from app.schemas.coupon import CouponBrief
from app.schemas.customer import AddressOut


class CheckoutPreview(BaseModel):
    """Order banne se pehle ka final hisaab. Is step me order nahi banta."""

    address: AddressOut
    stores: list[CartStoreGroup]  # dukaan-wise: har dukaan se kya uthana hai
    item_count: int
    items_subtotal: float  # saaman ka total (sirf available items)
    delivery_fee: float  # poore order par ek hi baar
    free_delivery_from: float  # itne ya zyada ke saaman par delivery free
    free_delivery_remaining: float  # free delivery ke liye aur kitna jodna hai (0 = free mil rahi hai)
    discount_amount: float = 0.0  # coupon ka discount (coupon na ho / na chale to 0)
    coupon: CouponBrief | None = None  # coupon laga ho to
    coupon_error: str | None = None  # coupon_code bheja par chala nahi: code (COUPON_EXPIRED, COUPON_MIN_ORDER...)
    coupon_message: str | None = None  # wahi, customer ki bhasha me
    total: float  # items_subtotal + delivery_fee - discount_amount
    can_checkout: bool
    blockers: list[str]  # CART_EMPTY / ITEM_UNAVAILABLE
