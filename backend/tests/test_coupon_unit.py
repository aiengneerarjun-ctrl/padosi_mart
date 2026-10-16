from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import require_super_admin
from app.api.v1 import admin_coupons
from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.coupon import CouponCreate, CouponPatch
from app.services.coupon_rules import MIN_PAYABLE, compute_discount, split_discount, window_problem

ZERO = "00000000-0000-0000-0000-000000000000"
LANGS = ("en", "hi", "bho")
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(days=10)


def _create(**kw):
    base = dict(code="save50", title="Save 50", discount_type="FLAT", value="50", expires_at=LATER)
    base.update(kw)
    return CouponCreate(**base)


# ---------- discount ka hisaab ----------

@pytest.mark.parametrize(
    "kind,value,cap,eligible,items,fee,expected",
    [
        ("FLAT", "50", None, "400", "400", "30", "50.00"),
        ("FLAT", "50", None, "30", "30", "30", "30.00"),  # discount saaman se zyada nahi
        ("PERCENT", "10", None, "400", "400", "30", "40.00"),
        ("PERCENT", "10", "25", "400", "400", "30", "25.00"),  # max limit
        ("PERCENT", "7.5", None, "333.33", "333.33", "30", "25.00"),  # 24.99975 -> aadha paisa upar
        ("FREE_DELIVERY", "0", None, "400", "400", "30", "30.00"),
        ("FREE_DELIVERY", "0", None, "900", "900", "0", "0.00"),  # delivery pehle se free: discount 0
        ("PERCENT", "100", None, "100", "100", "0", "99.00"),  # kam se kam Rs 1 dena hoga
        ("FLAT", "500", None, "100", "100", "30", "100.00"),
        ("PERCENT", "50", None, "200", "400", "30", "100.00"),  # sirf ek seller ke 200 par, poore order 400
    ],
)
def test_compute_discount(kind, value, cap, eligible, items, fee, expected):
    assert compute_discount(kind, D(value), D(cap) if cap else None, D(eligible), D(items), D(fee)) == D(expected)


def test_customer_always_pays_at_least_min_payable():
    for kind, value in (("FLAT", "1000"), ("PERCENT", "100"), ("FREE_DELIVERY", "0")):
        d = compute_discount(kind, D(value), None, D("50"), D("50"), D("30"))
        assert D("50") + D("30") - d >= MIN_PAYABLE


def test_split_sums_exactly_and_never_exceeds_a_part():
    parts = [("a", D("333.33")), ("b", D("333.33")), ("c", D("333.34"))]
    for disc in ("0.01", "1", "100", "33.33", "999.99", "1000"):
        out = split_discount(parts, D(disc))
        assert sum(out.values()) == min(D(disc), D("1000.00"))
        assert all(out[k] <= s for k, s in parts)
    assert split_discount(parts, D("0")) == {"a": D("0"), "b": D("0"), "c": D("0")}
    assert split_discount([], D("10")) == {}


def test_split_is_proportional():
    out = split_discount([("a", D("100")), ("b", D("300"))], D("40"))
    assert out == {"a": D("10.00"), "b": D("30.00")}


# ---------- samay aur sthiti ----------

def test_window_problem():
    assert window_problem(True, NOW - timedelta(days=1), LATER, NOW) is None
    assert window_problem(False, NOW - timedelta(days=1), LATER, NOW) == "COUPON_INACTIVE"
    assert window_problem(True, NOW + timedelta(hours=1), LATER, NOW) == "COUPON_NOT_STARTED"
    assert window_problem(True, NOW - timedelta(days=2), NOW, NOW) == "COUPON_EXPIRED"  # khatam hone ke pal par bhi expired


# ---------- admin ka input ----------

def test_create_normalises_code_and_defaults():
    c = _create(code="  save50 ")
    assert c.code == "SAVE50" and c.funded_by == "PLATFORM" and c.per_user_limit == 1 and c.is_public is True


@pytest.mark.parametrize(
    "kw",
    [
        {"code": "ab"}, {"code": "has space"}, {"code": "x" * 21},
        {"value": "0"},  # FLAT me value zaroori
        {"discount_type": "PERCENT", "value": "101"}, {"discount_type": "PERCENT", "value": "0"},
        {"discount_type": "FREE_DELIVERY", "value": "5"},
        {"max_discount": "10"},  # FLAT me max_discount nahi
        {"discount_type": "FREE_DELIVERY", "value": "0", "funded_by": "SELLER", "seller_id": ZERO},
        {"funded_by": "SELLER"},  # seller_id ke bina
        {"expires_at": datetime(2026, 1, 1)},  # timezone ke bina
        {"starts_at": LATER, "expires_at": NOW},
        {"per_user_limit": 0}, {"total_limit": 0}, {"min_order_amount": "-1"}, {"title": "  a "},
    ],
)
def test_create_rejects_bad_input(kw):
    with pytest.raises(ValidationError):
        _create(**kw)


def test_create_accepts_valid_variants():
    _create(discount_type="PERCENT", value="10", max_discount="100")
    _create(discount_type="FREE_DELIVERY", value="0")
    _create(funded_by="SELLER", seller_id=ZERO)


def test_patch_rules():
    assert CouponPatch(is_active=False, reason="band karna hai").is_active is False
    assert "total_limit" in CouponPatch(total_limit=None, reason="limit hatao").model_fields_set
    for kw in ({"reason": "karan"}, {"is_active": None, "reason": "karan"}, {"is_active": False}, {"is_active": False, "reason": "ab"}):
        with pytest.raises(ValidationError):
            CouponPatch(**kw)


# ---------- routes ----------

@pytest.mark.parametrize(
    "method,path",
    [("get", "/api/v1/coupons"), ("get", "/api/v1/checkout/preview?coupon_code=X")],
)
def test_customer_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_admin_coupon_routes_are_super_admin_only():
    assert any(d.dependency is require_super_admin for d in admin_coupons.router.dependencies)
    c = TestClient(app)
    for method, path in (("get", "/api/v1/admin/coupons"), ("post", "/api/v1/admin/coupons"), ("get", f"/api/v1/admin/coupons/{ZERO}"), ("patch", f"/api/v1/admin/coupons/{ZERO}")):
        assert getattr(c, method)(path).status_code == 401


# ---------- bhasha ----------

CODES = [
    "COUPON_NOT_FOUND", "COUPON_INACTIVE", "COUPON_NOT_STARTED", "COUPON_EXPIRED", "COUPON_MIN_ORDER", "COUPON_NOT_APPLICABLE",
    "COUPON_FIRST_ORDER_ONLY", "COUPON_USER_LIMIT", "COUPON_LIMIT_REACHED", "COUPON_NO_DISCOUNT", "COUPON_CODE_EXISTS",
    "COUPON_DATES_INVALID", "COUPON_LIMIT_TOO_LOW", "ORDER_NOTICE_COUPON_LOST",
]


@pytest.mark.parametrize("code", CODES)
def test_coupon_messages_in_all_languages(code):
    assert all(MESSAGES[code].get(lang) for lang in LANGS)


def test_coupon_lost_notice_placeholders_match():
    import string

    fields = {lang: {f for _, f, _, _ in string.Formatter().parse(MESSAGES["ORDER_NOTICE_COUPON_LOST"][lang]) if f} for lang in LANGS}
    assert fields["en"] == fields["hi"] == fields["bho"] == {"coupon", "amount"}


def test_coupon_lost_notice_renders_in_every_language():
    # order.py isi tarah bulata hai. translate_fmt ka pehla argument "code" hai, isliye placeholder ka naam "coupon" rakha hai.
    from app.core.i18n import translate_fmt

    for lang in LANGS:
        out = translate_fmt("ORDER_NOTICE_COUPON_LOST", lang, coupon="SAVE10", amount="30.00")
        assert "SAVE10" in out and "30.00" in out and "{" not in out
