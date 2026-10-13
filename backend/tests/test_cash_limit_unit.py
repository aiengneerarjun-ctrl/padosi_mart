from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.delivery_cash import LimitBody
from app.services.delivery_rules import DEFAULT_CASH_LIMIT, cash_limit_reached

ZERO = "00000000-0000-0000-0000-000000000000"


def test_default_limit_is_3000():
    assert DEFAULT_CASH_LIMIT == Decimal("3000.00")


@pytest.mark.parametrize(
    "in_hand,limit,expected",
    [
        (0, 3000, False),
        (2999.99, 3000, False),
        (3000, 3000, True),  # limit tak pahunch gaya = band
        (4500.50, 3000, True),
        (Decimal("2500"), Decimal("2500.00"), True),
        (0, 1, False),
    ],
)
def test_cash_limit_reached(in_hand, limit, expected):
    assert cash_limit_reached(in_hand, limit) is expected


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"cash_limit": "3000", "reason": "theek hai"}, True),
        ({"cash_limit": "100000", "reason": "abc"}, True),
        ({"cash_limit": "0", "reason": "abc"}, False),
        ({"cash_limit": "-10", "reason": "abc"}, False),
        ({"cash_limit": "100001", "reason": "abc"}, False),
        ({"cash_limit": "3000.123", "reason": "abc"}, False),  # 2 se zyada decimal
        ({"cash_limit": "3000"}, False),  # karan zaroori
        ({"cash_limit": "3000", "reason": "ab"}, False),
    ],
)
def test_limit_body(payload, ok):
    if ok:
        assert LimitBody(**payload).cash_limit == Decimal(payload["cash_limit"])
    else:
        with pytest.raises(ValidationError):
            LimitBody(**payload)


def test_message_in_all_languages():
    assert set(MESSAGES["CASH_LIMIT_REACHED"]) == {"en", "hi", "bho"}


def test_limit_route_needs_login():
    r = TestClient(app).patch(f"/api/v1/admin/delivery-cash/{ZERO}/limit", json={"cash_limit": "3000", "reason": "abc"})
    assert r.status_code == 401