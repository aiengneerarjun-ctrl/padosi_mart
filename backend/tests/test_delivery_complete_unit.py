import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.delivery_assignment import DeliverBody
from app.services.delivery_rules import OTP_LENGTH, OTP_LOCK_SECONDS, OTP_MAX_ATTEMPTS, delivery_otp, otp_matches

SECRET = "x" * 40


def test_otp_is_four_digits_and_stable():
    d = uuid.uuid4()
    otp = delivery_otp(SECRET, d)
    assert len(otp) == OTP_LENGTH == 4 and otp.isdigit()
    assert delivery_otp(SECRET, d) == otp  # roz wahi (database me save nahi hota)


def test_otp_depends_on_delivery_and_secret():
    ids = [uuid.uuid4() for _ in range(30)]
    assert len({delivery_otp(SECRET, i) for i in ids}) > 20  # alag delivery, alag OTP
    assert len({delivery_otp("y" * 40, i) for i in ids} & {delivery_otp(SECRET, i) for i in ids}) < 5  # secret badla to OTP badla


def test_otp_keeps_leading_zero():
    found = next(o for o in (delivery_otp(SECRET, uuid.uuid4()) for _ in range(500)) if o.startswith("0"))
    assert len(found) == 4  # "0427" jaisa OTP "427" nahi banta


def test_otp_matches_only_the_right_code():
    d = uuid.uuid4()
    right = delivery_otp(SECRET, d)
    wrong = f"{(int(right) + 1) % 10000:04d}"
    assert otp_matches(SECRET, d, right)
    assert not otp_matches(SECRET, d, wrong)
    assert not otp_matches(SECRET, d, right[:3])


def test_lock_settings_are_sane():
    assert 3 <= OTP_MAX_ATTEMPTS <= 10 and OTP_LOCK_SECONDS >= 300


@pytest.mark.parametrize("otp,ok", [("1234", True), ("0042", True), ("12", False), ("abcd", False), ("12345", False), ("12 4", False)])
def test_deliver_body_accepts_only_four_digits(otp, ok):
    if ok:
        assert DeliverBody(otp=otp).otp == otp
    else:
        with pytest.raises(ValidationError):
            DeliverBody(otp=otp)


def test_deliver_route_needs_login():
    r = TestClient(app).post("/api/v1/delivery/orders/00000000-0000-0000-0000-000000000000/deliver", json={"otp": "1234"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_new_error_codes_exist_in_all_languages():
    for code in ["OTP_INVALID", "OTP_LOCKED"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code