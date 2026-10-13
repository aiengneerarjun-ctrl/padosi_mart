from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import require_super_admin
from app.api.v1 import admin_delivery_earnings
from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.delivery_earnings import PayoutBody, RateBody
from app.services.delivery_rules import pick_rate

ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    "fee,expected",
    [(0, "45"), ("0.00", "45"), (D("0"), "45"), (30, "30"), (D("30.00"), "30"), (D("0.01"), "30")],
)
def test_pick_rate_free_delivery_vs_normal(fee, expected):
    assert pick_rate(fee, D("30"), D("45")) == D(expected)  # fee 0 = free-delivery rate (45), warna normal (30)


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"normal_rate": "30", "free_delivery_rate": "40", "reason": "naya rate"}, True),
        ({"normal_rate": "30", "reason": "sirf normal"}, True),
        ({"free_delivery_rate": "0", "reason": "free me kuch nahi"}, True),  # 0 theek hai
        ({"reason": "kuch nahi bheja"}, False),  # kam se kam ek rate chahiye
        ({"normal_rate": "-1", "reason": "abc"}, False),
        ({"normal_rate": "10001", "reason": "abc"}, False),
        ({"normal_rate": "30.123", "reason": "abc"}, False),  # paise me do ank se zyada nahi
        ({"normal_rate": "30"}, False),  # karan zaroori
        ({"normal_rate": "30", "reason": "ab"}, False),
    ],
)
def test_rate_body(payload, ok):
    if ok:
        assert RateBody(**payload).reason == payload["reason"]
    else:
        with pytest.raises(ValidationError):
            RateBody(**payload)


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"amount": "250.50"}, True),
        ({"amount": "-50", "note": "galti se zyada likh diya"}, True),
        ({"amount": "-50"}, False),  # sudhaar bina note ke nahi
        ({"amount": "0"}, False),
        ({"amount": "10.123"}, False),
    ],
)
def test_payout_body(payload, ok):
    if ok:
        assert PayoutBody(**payload).amount == D(payload["amount"])
    else:
        with pytest.raises(ValidationError):
            PayoutBody(**payload)


def test_payout_note_is_trimmed_and_blank_means_none():
    assert PayoutBody(amount="10", note="  paid  ").note == "paid"
    assert PayoutBody(amount="10", note="   ").note is None


def test_earnings_admin_router_is_super_admin_only():
    assert any(d.dependency is require_super_admin for d in admin_delivery_earnings.router.dependencies)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/delivery/me/earnings"),
        ("get", "/api/v1/admin/delivery-earnings"),
        ("get", "/api/v1/admin/delivery-earnings/rates"),
        ("patch", "/api/v1/admin/delivery-earnings/rates"),
        ("get", f"/api/v1/admin/delivery-earnings/{ZERO}"),
        ("post", f"/api/v1/admin/delivery-earnings/{ZERO}/payouts"),
    ],
)
def test_earnings_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_new_error_codes_exist_in_all_languages():
    for code in ["PAYOUT_EXCEEDS_DUE", "PAYOUT_CORRECTION_TOO_BIG"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code