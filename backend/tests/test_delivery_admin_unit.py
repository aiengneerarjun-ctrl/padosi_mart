import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import require_super_admin
from app.api.v1 import admin_deliveries
from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.delivery_admin import FailBody
from app.services.delivery_rules import FAIL_REASONS, fail_text, goods_in_hand

ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    "status,stores,expected",
    [
        ("ASSIGNED", ["READY_FOR_PICKUP", "PREPARING"], False),  # kuch nahi uthaya: order chhod sakte hain
        ("ASSIGNED", ["PICKED_UP", "PREPARING"], True),  # ek dukaan se uth chuka
        ("ASSIGNED", ["PICKED_UP", "REJECTED"], True),
        ("PICKED_UP", ["PICKED_UP"], True),
        ("OUT_FOR_DELIVERY", ["PICKED_UP", "PICKED_UP"], True),
        ("DELIVERED", ["PICKED_UP"], False),
        ("RELEASED", ["READY_FOR_PICKUP"], False),
        ("FAILED", ["PICKED_UP"], False),
    ],
)
def test_goods_in_hand(status, stores, expected):
    assert goods_in_hand(status, stores) is expected


def test_fail_text_and_reasons():
    assert fail_text("WRONG_ADDRESS", None) == "WRONG_ADDRESS"
    assert fail_text("OTHER", "gaadi kharab") == "OTHER: gaadi kharab"
    assert set(FAIL_REASONS) == {"CUSTOMER_UNREACHABLE", "CUSTOMER_REFUSED", "WRONG_ADDRESS", "PARTNER_ISSUE", "OTHER"}


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"reason_code": "CUSTOMER_UNREACHABLE"}, True),
        ({"reason_code": "OTHER", "note": "gaadi kharab ho gayi"}, True),
        ({"reason_code": "OTHER"}, False),  # OTHER bina note ke nahi
        ({"reason_code": "BAHANA"}, False),  # list ke bahar ka karan
    ],
)
def test_fail_body(payload, ok):
    if ok:
        assert FailBody(**payload).reason_code == payload["reason_code"]
    else:
        with pytest.raises(ValidationError):
            FailBody(**payload)


def test_admin_deliveries_router_is_super_admin_only():
    assert any(d.dependency is require_super_admin for d in admin_deliveries.router.dependencies)


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", f"/api/v1/delivery/orders/{ZERO}/fail"),
        ("get", "/api/v1/admin/deliveries"),
        ("post", f"/api/v1/admin/deliveries/{ZERO}/release"),
        ("post", f"/api/v1/admin/deliveries/{ZERO}/fail"),
        ("post", f"/api/v1/admin/deliveries/{ZERO}/unlock-otp"),
    ],
)
def test_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_new_error_codes_exist_in_all_languages():
    for code in ["NOTHING_PICKED_UP", "GOODS_IN_HAND"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code