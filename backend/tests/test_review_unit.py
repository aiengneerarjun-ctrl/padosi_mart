import string
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.review import ReviewCreate
from app.services.review import REVIEW_WINDOW_DAYS, first_name, review_deadline, summarize

LANGS = ("en", "hi", "bho")
ZERO = "00000000-0000-0000-0000-000000000000"
CODES = ["REVIEWER_ANONYMOUS", "REVIEW_ORDER_NOT_DELIVERED", "REVIEW_WINDOW_OVER", "REVIEW_ALREADY_EXISTS", "REVIEW_TARGET_NOT_FOUND", "REVIEW_NOT_FOUND"]


@pytest.mark.parametrize("code", CODES)
def test_review_messages_in_all_languages(code):
    assert all(MESSAGES[code].get(lang) for lang in LANGS)
    fields = {lang: {f for _, f, _, _ in string.Formatter().parse(MESSAGES[code][lang]) if f} for lang in LANGS}
    assert fields["en"] == fields["hi"] == fields["bho"]


def test_summarize_empty_and_average():
    s = summarize({})
    assert s.average is None and s.count == 0 and s.stars == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    s = summarize({5: 1, 2: 1})  # (5 + 2) / 2
    assert s.average == 3.5 and s.count == 2
    s = summarize({5: 2, 4: 1})  # 14 / 3 = 4.666..
    assert s.average == 4.67
    assert summarize({1: 1}).average == 1.0


def test_first_name_only_and_fallback():
    assert first_name("Ramesh Kumar Singh", "en") == "Ramesh"
    assert first_name("  ", "en") == "Customer" and first_name(None, "hi") == MESSAGES["REVIEWER_ANONYMOUS"]["hi"]
    assert len(first_name("A" * 100, "en")) == 30


def test_review_window_is_seven_days():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert REVIEW_WINDOW_DAYS == 7 and review_deadline(t) == t + timedelta(days=7)


def test_review_create_schema_rules():
    oid = uuid.uuid4()
    assert ReviewCreate(order_id=oid, target="STORE", store_id=uuid.uuid4(), rating=5, comment="  accha  ").comment == "accha"
    assert ReviewCreate(order_id=oid, target="PARTNER", rating=1, comment="   ").comment is None  # khali = comment nahi
    for bad in (
        dict(target="STORE", rating=5),  # store_id nahi
        dict(target="PARTNER", store_id=uuid.uuid4(), rating=5),  # partner ke saath store_id
        dict(target="PARTNER", rating=0), dict(target="PARTNER", rating=6),
        dict(target="PARTNER", rating=3, comment="x" * 501), dict(target="SELLER", rating=3),
    ):
        with pytest.raises(ValidationError):
            ReviewCreate(order_id=oid, **bad)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", f"/api/v1/orders/{ZERO}/reviewable"), ("post", "/api/v1/reviews"), ("get", "/api/v1/reviews/mine"),
        ("get", f"/api/v1/shop/stores/{ZERO}/reviews"), ("get", "/api/v1/seller/reviews"), ("get", "/api/v1/delivery/reviews"),
        ("get", "/api/v1/admin/reviews"), ("post", f"/api/v1/admin/reviews/{ZERO}/hide"), ("post", f"/api/v1/admin/reviews/{ZERO}/unhide"),
    ],
)
def test_review_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path, **({"json": {}} if method == "post" else {}))
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"
