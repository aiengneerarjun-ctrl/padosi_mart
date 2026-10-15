from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import require_super_admin
from app.api.v1 import admin_payments
from app.core.config import Settings
from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.payment import AdminRefundBody
from app.services import cashfree
from app.services.payment import _event_key, _map_status

ZERO = "00000000-0000-0000-0000-000000000000"
SECRET = "abc123secret"


def test_signature_roundtrip_and_tamper():
    raw = b'{"type":"PAYMENT_SUCCESS_WEBHOOK","data":{"order":{"order_id":"PD1001"}}}'
    sig = cashfree.sign(SECRET, "1760000000000", raw)
    assert cashfree.verify_signature("1760000000000", raw, sig, secret=SECRET)
    assert not cashfree.verify_signature("1760000000001", raw, sig, secret=SECRET)  # timestamp badla
    assert not cashfree.verify_signature("1760000000000", raw + b" ", sig, secret=SECRET)  # body badla
    assert not cashfree.verify_signature("1760000000000", raw, sig, secret="galat")  # secret alag
    assert not cashfree.verify_signature(None, raw, sig, secret=SECRET)
    assert not cashfree.verify_signature("1760000000000", raw, None, secret=SECRET)
    assert not cashfree.verify_signature("1760000000000", raw, sig, secret="")  # secret khali = hamesha galat


def test_signature_is_base64_hmac_sha256_of_timestamp_plus_raw_body():
    import base64
    import hashlib
    import hmac

    raw = b'{"a":1}'
    expected = base64.b64encode(hmac.new(b"k", b"123" + raw, hashlib.sha256).digest()).decode()
    assert cashfree.sign("k", "123", raw) == expected


@pytest.mark.parametrize(
    "status,expected",
    [("SUCCESS", "SUCCESS"), ("success", "SUCCESS"), ("PENDING", "PENDING"), ("ONHOLD", "PENDING"), (None, "PENDING"),
     ("CANCELLED", "FAILED"), ("FAILED", "FAILED"), ("kuch aur", "PENDING")],
)
def test_map_refund_status(status, expected):
    assert _map_status(status) == expected


def test_event_key_payment_refund_and_fallback():
    p = {"payment": {"cf_payment_id": 77, "payment_status": "SUCCESS"}}
    assert _event_key("PAYMENT_SUCCESS_WEBHOOK", p, b"x") == "PAYMENT_SUCCESS_WEBHOOK:77:SUCCESS"
    r = {"refund": {"refund_id": "RF1", "refund_status": "SUCCESS"}}
    assert _event_key("REFUND_STATUS_WEBHOOK", r, b"x") == "REFUND_STATUS_WEBHOOK:RF1:SUCCESS"
    assert _event_key("WEBHOOK", {}, b"x").startswith("raw:")  # Cashfree ka test webhook
    assert _event_key("WEBHOOK", {}, b"x") == _event_key("WEBHOOK", {}, b"x")
    assert _event_key("WEBHOOK", {}, b"x") != _event_key("WEBHOOK", {}, b"y")
    # PENDING aur SUCCESS alag event hain
    assert _event_key("REFUND_STATUS_WEBHOOK", {"refund": {"refund_id": "RF1", "refund_status": "PENDING"}}, b"") != _event_key("REFUND_STATUS_WEBHOOK", r, b"")


@pytest.mark.parametrize("phone,expected", [("9876543210", "9876543210"), ("+919876543210", "9876543210"), ("91 98765-43210", "9876543210")])
def test_customer_phone_is_last_10_digits(phone, expected):
    assert cashfree.customer_phone(phone) == expected


def _settings(**kw):
    base = dict(postgres_user="u", postgres_password="p", postgres_db="d", jwt_secret="s" * 32, _env_file=None)
    return Settings(**base, **kw)


def test_payments_enabled_needs_all_three():
    assert _settings().payments_enabled is False
    assert _settings(cashfree_client_id="a", cashfree_client_secret="b").payments_enabled is False  # notify url nahi
    assert _settings(cashfree_client_id="a", payment_notify_url="https://x").payments_enabled is False  # secret nahi
    assert _settings(cashfree_client_id="a", cashfree_client_secret="b", payment_notify_url="https://x/hook").payments_enabled is True
    s = _settings()
    assert s.cashfree_env == "sandbox" and s.payment_window_minutes == 15 and s.cashfree_api_version


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"amount": "50", "note": "delivery fail hui"}, True),
        ({"amount": "0.01", "note": "abc"}, True),
        ({"amount": "0", "note": "abc"}, False),
        ({"amount": "-5", "note": "abc"}, False),
        ({"amount": "10.123", "note": "abc"}, False),
        ({"amount": "10"}, False),
        ({"amount": "10", "note": "ab"}, False),
    ],
)
def test_admin_refund_body(payload, ok):
    if ok:
        assert AdminRefundBody(**payload).amount == D(payload["amount"])
    else:
        with pytest.raises(ValidationError):
            AdminRefundBody(**payload)


def test_admin_router_is_super_admin_only():
    assert any(d.dependency is require_super_admin for d in admin_payments.router.dependencies)


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", f"/api/v1/orders/{ZERO}/pay"),
        ("get", f"/api/v1/admin/payments/orders/{ZERO}"),
        ("post", f"/api/v1/admin/payments/orders/{ZERO}/refunds"),
        ("get", "/api/v1/admin/payments/refunds"),
        ("post", f"/api/v1/admin/payments/refunds/{ZERO}/retry"),
        ("post", "/api/v1/admin/payments/expire-unpaid"),
    ],
)
def test_payment_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_webhook_without_valid_signature_is_rejected():
    c = TestClient(app)
    r = c.post("/api/v1/payments/cashfree/webhook", content=b"{}")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "INVALID_SIGNATURE"
    r = c.post("/api/v1/payments/cashfree/webhook", content=b"{}", headers={"x-webhook-signature": "x", "x-webhook-timestamp": "1"})
    assert r.status_code == 401


def test_error_codes_in_all_languages():
    codes = ["PAYMENT_NOT_ALLOWED", "PAYMENT_ALREADY_PAID", "PAYMENT_EXPIRED", "PAYMENT_PROVIDER_ERROR", "PAYMENT_NOT_FOUND",
             "INVALID_SIGNATURE", "INVALID_WEBHOOK", "REFUND_EXCEEDS_PAID", "REFUND_NOT_FOUND"]
    for code in codes:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code