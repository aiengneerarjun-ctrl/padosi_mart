import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.order import Order, OrderStatus, PaymentMethod, StoreOrderStatus
from app.schemas.order import OrderCreate

KEY = {"Idempotency-Key": "abcdefgh12345678"}


def test_order_number_format():
    o = Order(order_no=1001)
    assert o.order_number == "PD1001"


def test_status_lists_match_spec():
    assert OrderStatus.PLACED == "PLACED" and OrderStatus.FAILED_DELIVERY == "FAILED_DELIVERY"
    assert len(list(OrderStatus)) == 15
    assert StoreOrderStatus.READY_FOR_PICKUP == "READY_FOR_PICKUP"
    assert PaymentMethod.COD == "COD"


def test_order_create_defaults_and_validation():
    o = OrderCreate(expected_total="130.00")
    assert o.payment_method == "COD" and o.expected_total == Decimal("130.00") and o.address_id is None
    for bad in [{"expected_total": -1}, {"expected_total": "1.234"}, {"payment_method": "CARD"}, {"note": "x" * 301}]:
        with pytest.raises(ValidationError):
            OrderCreate(**{"expected_total": 10, **bad})


@pytest.mark.parametrize(
    "method,path",
    [("post", "/api/v1/orders"), ("get", "/api/v1/orders"), ("get", f"/api/v1/orders/{uuid.uuid4()}"), ("post", f"/api/v1/orders/{uuid.uuid4()}/cancel")],
)
def test_orders_need_login(method, path):
    r = getattr(TestClient(app), method)(path, headers=KEY)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"