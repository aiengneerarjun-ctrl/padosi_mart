from pydantic import BaseModel

from app.schemas.cart import CartStoreGroup
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
    total: float  # items_subtotal + delivery_fee
    can_checkout: bool
    blockers: list[str]  # CART_EMPTY / ITEM_UNAVAILABLE