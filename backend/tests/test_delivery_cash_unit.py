from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import require_super_admin
from app.api.v1 import admin_delivery_cash
from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.delivery_cash import DepositBody
from app.services.delivery_rules import deposit_problem


@pytest.mark.parametrize(
    "collected,deposited,amount,expected",
    [
        ("500", "0", "500", None),  # poora jama
        ("500", "0", "500.01", "EXCEEDS"),
        ("500", "200", "300", None),
        ("500", "200", "300.01", "EXCEEDS"),
        ("500", "200", "-200", None),  # sudhaar: jitna jama hua tha utna wapas
        ("500", "200", "-200.01", "BELOW_ZERO"),
        ("500", "0", "0", "ZERO"),
    ],
)
def test_deposit_problem(collected, deposited, amount, expected):
    assert deposit_problem(D(collected), D(deposited), D(amount)) == expected


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"amount": "250.50"}, True),
        ({"amount": "-50", "note": "galti se zyada likh diya"}, True),
        ({"amount": "-50"}, False),  # sudhaar bina note ke nahi
        ({"amount": "0"}, False),
        ({"amount": "10.123"}, False),  # paise me do ank se zyada nahi
    ],
)
def test_deposit_body(payload, ok):
    if ok:
        assert DepositBody(**payload).amount == D(payload["amount"])
    else:
        with pytest.raises(ValidationError):
            DepositBody(**payload)


def test_deposit_note_is_trimmed_and_blank_note_means_none():
    assert DepositBody(amount="10", note="  hello  ").note == "hello"
    assert DepositBody(amount="10", note="   ").note is None


def test_cash_admin_router_is_super_admin_only():
    assert any(d.dependency is require_super_admin for d in admin_delivery_cash.router.dependencies)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/delivery/me/cash"),
        ("get", "/api/v1/admin/delivery-cash"),
        ("get", "/api/v1/admin/delivery-cash/00000000-0000-0000-0000-000000000000"),
        ("post", "/api/v1/admin/delivery-cash/00000000-0000-0000-0000-000000000000/deposits"),
    ],
)
def test_cash_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_new_error_codes_exist_in_all_languages():
    for code in ["DEPOSIT_EXCEEDS_CASH", "DEPOSIT_CORRECTION_TOO_BIG"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code