from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import require_super_admin
from app.api.v1 import admin_settlements
from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.settlement import SellerPayoutBody, SettlementRateBody
from app.services.settlement_rules import commission_amount, rate_for_store_type

ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    "subtotal,rate,expected",
    [
        ("500", "5", "25.00"),
        ("400", "10", "40.00"),
        ("333.33", "5", "16.67"),  # 16.6665 -> aadha paisa upar
        ("100", "0", "0.00"),
        ("100", "100", "100.00"),  # commission bikri se zyada kabhi nahi
        ("0", "10", "0.00"),
        (D("999.99"), D("2.50"), "25.00"),  # 24.99975 -> 25.00
        ("10.10", "7.5", "0.76"),  # 0.7575 -> 0.76
    ],
)
def test_commission_amount(subtotal, rate, expected):
    assert commission_amount(subtotal, rate) == D(expected)


@pytest.mark.parametrize(
    "store_type,expected",
    [("KIRANA", "5"), ("RESTAURANT", "10"), (None, "5"), ("SOMETHING", "5")],
)
def test_rate_for_store_type(store_type, expected):
    assert rate_for_store_type(store_type, D("5"), D("10")) == D(expected)


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"kirana_rate": "5", "restaurant_rate": "10", "reason": "naya rate"}, True),
        ({"kirana_rate": "0", "reason": "mufat"}, True),
        ({"restaurant_rate": "100", "reason": "poora"}, True),
        ({"reason": "kuch nahi bheja"}, False),
        ({"kirana_rate": "-1", "reason": "abc"}, False),
        ({"kirana_rate": "100.01", "reason": "abc"}, False),
        ({"kirana_rate": "5.123", "reason": "abc"}, False),
        ({"kirana_rate": "5"}, False),
        ({"kirana_rate": "5", "reason": "ab"}, False),
    ],
)
def test_rate_body(payload, ok):
    if ok:
        assert SettlementRateBody(**payload).reason == payload["reason"]
    else:
        with pytest.raises(ValidationError):
            SettlementRateBody(**payload)


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"amount": "250.50"}, True),
        ({"amount": "-50", "note": "galti se zyada likh diya"}, True),
        ({"amount": "-50"}, False),
        ({"amount": "0"}, False),
        ({"amount": "10.123"}, False),
    ],
)
def test_payout_body(payload, ok):
    if ok:
        assert SellerPayoutBody(**payload).amount == D(payload["amount"])
    else:
        with pytest.raises(ValidationError):
            SellerPayoutBody(**payload)


def test_admin_router_is_super_admin_only():
    assert any(d.dependency is require_super_admin for d in admin_settlements.router.dependencies)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/seller/earnings"),
        ("get", "/api/v1/admin/seller-settlements"),
        ("get", "/api/v1/admin/seller-settlements/rates"),
        ("patch", "/api/v1/admin/seller-settlements/rates"),
        ("get", f"/api/v1/admin/seller-settlements/{ZERO}"),
        ("post", f"/api/v1/admin/seller-settlements/{ZERO}/payouts"),
    ],
)
def test_settlement_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_error_codes_in_all_languages():
    for code in ["SETTLEMENT_EXCEEDS_DUE", "SETTLEMENT_CORRECTION_TOO_BIG"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code