"""Delivery partner ke seedhe niyam. Is file me DB / FastAPI ka kuch nahi, isliye test karna aasaan hai."""
import hashlib
import hmac
import re
from decimal import Decimal

VEHICLE_TYPES = ("BICYCLE", "BIKE", "SCOOTER")
NEEDS_VEHICLE_NUMBER = ("BIKE", "SCOOTER")  # cycle ka number nahi hota
ID_TYPES = ("AADHAAR", "PAN")
STATUSES = ("PENDING", "ACTIVE", "REJECTED", "SUSPENDED")

# Admin action -> (kin status se ho sakta hai, kaunse status par jaata hai)
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "approve": (("PENDING",), "ACTIVE"),
    "reject": (("PENDING",), "REJECTED"),
    "suspend": (("ACTIVE",), "SUSPENDED"),
    "reactivate": (("SUSPENDED",), "ACTIVE"),
}

_PLATE = re.compile(r"^[A-Z0-9]{6,12}$")


def can_move(action: str, current: str) -> bool:
    rule = TRANSITIONS.get(action)
    return rule is not None and current in rule[0]


def normalize_vehicle_number(raw: str | None) -> str | None:
    """'br 01-ab 1234' -> 'BR01AB1234'. Khali ho to None. Galat ho to ValueError."""
    if raw is None:
        return None
    cleaned = re.sub(r"[\s\-.]", "", raw).upper()
    if not cleaned:
        return None
    if not _PLATE.match(cleaned):
        raise ValueError("vehicle number sahi nahi hai")
    return cleaned



# ---------------- delivery (order assignment) ----------------
DELIVERY_STATUSES = ("ASSIGNED", "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED", "RELEASED", "FAILED")
ACTIVE_DELIVERY_STATUSES = ("ASSIGNED", "PICKED_UP", "OUT_FOR_DELIVERY")  # partner abhi inme busy hai
MAX_CANDIDATES = 100  # ek baar me itne "ready" orders hi dekhte aur doori se lagate hain


def cod_amount_due(payment_method: str, payment_status: str, order_status: str, total) -> float:
    """COD order me delivery par partner ko customer se kitna cash lena hai (paid/cancelled/online me 0)."""
    owes = payment_method == "COD" and payment_status == "PENDING" and order_status != "CANCELLED"
    return float(total) if owes else 0.0

# Order customer ke order karte hi (CONFIRMED se) nazdeek ke partners ko dikhta hai, READY_FOR_PICKUP tak.
OPEN_ORDER_STATUSES = ("CONFIRMED", "SELLER_ACCEPTED", "PREPARING", "READY_FOR_PICKUP")
NEARBY_RADIUS_KM = 3.0  # partner se sabse paas wali dukaan itni doori tak ho to hi order dikhega / accept hoga


def order_status_when_assigned(current: str) -> str:
    """Partner ne accept kiya. Dukaan abhi tayyari me ho to Order ka status wahi rehta hai (seller ka rollup na bigde);
    sab tayyar ho to DELIVERY_ASSIGNED."""
    return "DELIVERY_ASSIGNED" if current == "READY_FOR_PICKUP" else current


def order_status_when_released(current: str) -> str:
    return "READY_FOR_PICKUP" if current == "DELIVERY_ASSIGNED" else current


# ---------------- pickup / out for delivery ----------------
_DEAD_STORE = ("REJECTED", "CANCELLED")


def can_pickup_store(store_status: str) -> bool:
    """Dukaan se saaman tabhi uthega jab seller ne READY_FOR_PICKUP kar diya ho."""
    return store_status == "READY_FOR_PICKUP"


def all_stores_picked_up(store_statuses: list[str]) -> bool:
    """Reject / cancel hui dukaanein ginti me nahi. Koi dukaan active na ho to False."""
    live = [s for s in store_statuses if s not in _DEAD_STORE]
    return bool(live) and all(s == "PICKED_UP" for s in live)


# ---------------- delivery OTP ----------------
OTP_LENGTH = 4
OTP_MAX_ATTEMPTS = 5  # itni galat koshish ke baad thodi der ke liye band
OTP_LOCK_SECONDS = 600


def delivery_otp(secret: str, delivery_id) -> str:
    """Delivery ka 4 ank ka OTP. Database me save nahi hota: secret + delivery id se roz wahi banta hai,
    isliye customer ko dikha sakte hain aur partner ke daale hue se match kar sakte hain."""
    digest = hmac.new(secret.encode(), f"delivery-otp:{delivery_id}".encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:4], 'big') % 10**OTP_LENGTH:0{OTP_LENGTH}d}"


def otp_matches(secret: str, delivery_id, given: str) -> bool:
    return hmac.compare_digest(delivery_otp(secret, delivery_id), given)


# ---------------- COD cash ka hisaab ----------------
def deposit_problem(collected: Decimal, deposited: Decimal, amount: Decimal) -> str | None:
    """Admin ne partner se cash liya (amount > 0) ya galti sudhari (amount < 0). Kuch galat ho to code, warna None.
    cash_in_hand = collected - deposited. Na jama kiya hua cash_in_hand se zyada ho, na sudhaar jama kiye se zyada."""
    if amount == 0:
        return "ZERO"
    if deposited + amount < 0:
        return "BELOW_ZERO"  # sudhaar jitna jama hua tha usse zyada
    if collected - (deposited + amount) < 0:
        return "EXCEEDS"  # partner ke paas jitna cash hai usse zyada jama dikha diya
    return None