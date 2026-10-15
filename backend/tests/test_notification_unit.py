import uuid
from datetime import datetime, timezone
from string import Formatter

import pytest
from fastapi.testclient import TestClient

from app.core.i18n import MESSAGES
from app.main import app
from app.models import Notification
from app.services.notification import ORDER_STATUS_NOTIFICATIONS, render

ZERO = "00000000-0000-0000-0000-000000000000"
LANGS = ("en", "hi", "bho")
# Har notification code aur uske text me kaun kaun se khali jagah (params) hone chahiye
CODES = {
    "ORDER_ACCEPTED": {"order_no"},
    "ORDER_PARTNER_ASSIGNED": {"order_no"},
    "ORDER_OUT_FOR_DELIVERY": {"order_no"},
    "ORDER_DELIVERED": {"order_no"},
    "ORDER_CANCELLED": {"order_no"},
    "ORDER_FAILED_DELIVERY": {"order_no"},
    "ORDER_ITEMS_REMOVED": {"order_no", "store_name", "count", "minutes"},
    "SELLER_NEW_ORDER": {"order_no", "store_name"},
    "PAYOUT_RECEIVED": {"amount"},
    "SELLER_PAYOUT_RECEIVED": {"amount"},
}


def _fields(text: str) -> set[str]:
    return {f for _, f, _, _ in Formatter().parse(text) if f}


def _note(code: str, params: dict) -> Notification:
    return Notification(id=uuid.uuid4(), user_id=uuid.uuid4(), code=code, params=params, order_id=None, read_at=None, created_at=datetime.now(timezone.utc))


@pytest.mark.parametrize("code", sorted(CODES))
def test_every_code_has_title_and_body_in_all_languages(code):
    for part in ("TITLE", "BODY"):
        entry = MESSAGES[f"NOTIF_{code}_{part}"]
        assert all(entry.get(lang) for lang in LANGS), (code, part)


@pytest.mark.parametrize("code", sorted(CODES))
def test_same_placeholders_in_every_language(code):
    for lang in LANGS:  # kisi bhasha me param chhoot / badal na jaye
        assert _fields(MESSAGES[f"NOTIF_{code}_BODY"][lang]) <= CODES[code], (code, lang)
    assert len({frozenset(_fields(MESSAGES[f"NOTIF_{code}_BODY"][lang])) for lang in LANGS}) == 1, code


def test_every_customer_status_notification_has_text():
    for code in ORDER_STATUS_NOTIFICATIONS.values():
        assert code in CODES


def test_status_map_covers_expected_statuses_only():
    assert set(ORDER_STATUS_NOTIFICATIONS) == {
        "SELLER_ACCEPTED", "DELIVERY_ASSIGNED", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "FAILED_DELIVERY",
    }


def test_render_fills_params_in_each_language():
    n = _note("ORDER_ITEMS_REMOVED", {"order_no": "PD1001", "store_name": "Shyam", "count": 2, "minutes": 2})
    for lang in LANGS:
        out = render(n, lang)
        assert "{" not in out.body and "PD1001" in out.body and "Shyam" in out.body and out.title
        assert out.is_read is False and out.read_at is None
    assert render(n, "hi").body != render(n, "en").body


def test_render_missing_param_does_not_crash():
    out = render(_note("ORDER_DELIVERED", {}), "en")
    assert "{order_no}" in out.body  # khali jagah dikhe, error nahi


def test_render_unknown_code_falls_back_to_code():
    out = render(_note("SOMETHING_NEW", {}), "hi")
    assert out.title == "SOMETHING_NEW" and out.body == ""


def test_render_read_flag():
    n = _note("ORDER_DELIVERED", {"order_no": "PD1"})
    n.read_at = datetime.now(timezone.utc)
    assert render(n, "en").is_read is True


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/notifications"),
        ("get", "/api/v1/notifications/unread-count"),
        ("post", "/api/v1/notifications/read-all"),
        ("post", f"/api/v1/notifications/{ZERO}/read"),
    ],
)
def test_notification_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_not_found_message_in_all_languages():
    assert all(MESSAGES["NOTIFICATION_NOT_FOUND"].get(lang) for lang in LANGS)