import string

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.support import MessageBody, TicketCreate
from app.services.notification import render
from app.services.support import MAX_MESSAGES, MAX_OPEN_TICKETS, PREVIEW_CHARS, has_role, preview

LANGS = ("en", "hi", "bho")
ZERO = "00000000-0000-0000-0000-000000000000"
CODES = ["TICKET_NOT_FOUND", "TICKET_CLOSED", "TICKET_LIMIT", "TICKET_MESSAGE_LIMIT", "TICKET_ROLE_NOT_ALLOWED"]
NOTIFS = ["TICKET_REPLIED", "TICKET_CLOSED"]


@pytest.mark.parametrize("code", CODES + [f"NOTIF_{n}_{p}" for n in NOTIFS for p in ("TITLE", "BODY")])
def test_support_messages_in_all_languages(code):
    assert all(MESSAGES[code].get(lang) for lang in LANGS)
    fields = {lang: {f for _, f, _, _ in string.Formatter().parse(MESSAGES[code][lang]) if f} for lang in LANGS}
    assert fields["en"] == fields["hi"] == fields["bho"]


@pytest.mark.parametrize("code", NOTIFS)
def test_ticket_notifications_render(code):
    from datetime import datetime, timezone
    import uuid

    from app.models import Notification

    n = Notification(id=uuid.uuid4(), user_id=uuid.uuid4(), code=code, params={"ticket_no": "TK1001"}, order_id=None, read_at=None, created_at=datetime.now(timezone.utc))
    for lang in LANGS:
        out = render(n, lang)
        assert "TK1001" in out.body and "{" not in out.body and out.title != code


def test_notification_codes_fit_the_column():
    assert all(len(c) <= 40 for c in NOTIFS)  # notifications.code String(40)


def test_has_role_rules():
    assert has_role(["CUSTOMER"], "CUSTOMER") and not has_role(["CUSTOMER"], "SELLER") and not has_role(["CUSTOMER"], "DELIVERY_PARTNER")
    assert has_role(["CUSTOMER", "SELLER"], "SELLER") and has_role(["RESTAURANT"], "SELLER")
    assert has_role(["DELIVERY_PARTNER"], "DELIVERY_PARTNER") and not has_role([], "CUSTOMER")
    assert not has_role(["SUPER_ADMIN"], "CUSTOMER")  # admin ticket nahi kholta


def test_limits_and_preview():
    assert MAX_OPEN_TICKETS == 5 and MAX_MESSAGES == 100
    assert preview("  hello \n  world  ") == "hello world"
    long = preview("a" * 500)
    assert len(long) == PREVIEW_CHARS and long.endswith("…")


def test_ticket_schema_rules():
    ok = TicketCreate(category="PAYMENT", subject="  Paisa kat gaya  ", message="  dekhiye  ")
    assert ok.subject == "Paisa kat gaya" and ok.message == "dekhiye" and ok.raised_as == "CUSTOMER" and ok.order_id is None
    for bad in (
        dict(category="PAYMENT", subject="ab", message="x"), dict(category="PAYMENT", subject="theek hai", message="   "),
        dict(category="PAYMENT", subject="theek hai", message="x" * 2001), dict(category="MAGIC", subject="theek hai", message="x"),
        dict(category="OTHER", subject="theek hai", message="x", raised_as="SUPER_ADMIN"),
    ):
        with pytest.raises(ValidationError):
            TicketCreate(**bad)
    with pytest.raises(ValidationError):
        MessageBody(body="   ")


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/support/tickets"), ("get", "/api/v1/support/tickets"), ("get", f"/api/v1/support/tickets/{ZERO}"),
        ("post", f"/api/v1/support/tickets/{ZERO}/messages"), ("post", f"/api/v1/support/tickets/{ZERO}/close"),
        ("get", "/api/v1/admin/support/tickets"), ("get", f"/api/v1/admin/support/tickets/{ZERO}"),
        ("post", f"/api/v1/admin/support/tickets/{ZERO}/messages"), ("post", f"/api/v1/admin/support/tickets/{ZERO}/close"),
        ("post", f"/api/v1/admin/support/tickets/{ZERO}/reopen"),
    ],
)
def test_support_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path, **({"json": {}} if method == "post" else {}))
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"
