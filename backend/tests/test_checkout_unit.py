from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.checkout import DELIVERY_FEE, FREE_DELIVERY_FROM, delivery_fee_for, free_delivery_remaining


def test_free_delivery_threshold_is_799():
    assert FREE_DELIVERY_FROM == Decimal("799")


@pytest.mark.parametrize(
    "subtotal,fee",
    [("0", "0"), ("1", None), ("798.99", None), ("799", "0"), ("799.01", "0"), ("2000", "0")],
)
def test_delivery_fee(subtotal, fee):
    expected = DELIVERY_FEE if fee is None else Decimal(fee)
    assert delivery_fee_for(Decimal(subtotal)) == expected


def test_free_delivery_remaining():
    assert free_delivery_remaining(Decimal("700")) == Decimal("99")
    assert free_delivery_remaining(Decimal("799")) == 0
    assert free_delivery_remaining(Decimal("900")) == 0


def test_checkout_needs_login():
    r = TestClient(app).get("/api/v1/checkout/preview")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"