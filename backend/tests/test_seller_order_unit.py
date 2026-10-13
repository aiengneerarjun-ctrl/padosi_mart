import re
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.i18n import MESSAGES, SUPPORTED, translate, translate_fmt
from app.main import app
from app.models.order import OrderStatus, RemovalReason
from app.schemas.seller_order import RejectBody, UnavailableBody
from app.services.seller_order import can_move, rollup_status


@pytest.mark.parametrize(
    "cur,target,ok",
    [
        ("PLACED", "SELLER_ACCEPTED", True), ("PLACED", "REJECTED", True), ("PLACED", "PREPARING", False),
        ("PLACED", "READY_FOR_PICKUP", False), ("SELLER_ACCEPTED", "PREPARING", True), ("SELLER_ACCEPTED", "READY_FOR_PICKUP", True),
        ("SELLER_ACCEPTED", "REJECTED", False), ("PREPARING", "READY_FOR_PICKUP", True), ("PREPARING", "SELLER_ACCEPTED", False),
        ("READY_FOR_PICKUP", "PREPARING", False), ("REJECTED", "SELLER_ACCEPTED", False), ("CANCELLED", "SELLER_ACCEPTED", False),
    ],
)
def test_transitions(cur, target, ok):
    assert can_move(cur, target) is ok


def test_rollup_is_least_advanced_store():
    assert rollup_status(["PLACED", "SELLER_ACCEPTED"]) is None  # ek ne accept nahi kiya
    assert rollup_status(["SELLER_ACCEPTED", "SELLER_ACCEPTED"]) == OrderStatus.SELLER_ACCEPTED
    assert rollup_status(["PREPARING", "READY_FOR_PICKUP"]) == OrderStatus.PREPARING
    assert rollup_status(["READY_FOR_PICKUP", "READY_FOR_PICKUP"]) == OrderStatus.READY_FOR_PICKUP
    assert rollup_status(["REJECTED", "PREPARING"]) == OrderStatus.PREPARING  # reject hui dukaan ginti me nahi
    assert rollup_status(["REJECTED", "CANCELLED"]) is None
    assert rollup_status(["PLACED", "REJECTED"]) is None


def test_unavailable_body_rules():
    one = {"item_id": str(uuid.uuid4())}
    assert UnavailableBody(items=[one]).items[0].reason == "OUT_OF_STOCK"  # default karan
    with pytest.raises(ValidationError):
        UnavailableBody(items=[])
    with pytest.raises(ValidationError):
        UnavailableBody(items=[one, one])  # ek item do baar nahi
    with pytest.raises(ValidationError):
        UnavailableBody(items=[{**one, "reason": "BORED"}])
    with pytest.raises(ValidationError):
        UnavailableBody(items=[{**one, "note": "x" * 201}])


def test_reject_body_needs_reason():
    assert RejectBody(reason="saaman nahi hai").reason_code == "OTHER"
    with pytest.raises(ValidationError):
        RejectBody(reason="ab")


def test_every_removal_reason_has_a_message_in_all_languages():
    for reason in RemovalReason:
        for lang in SUPPORTED:
            assert translate(f"REMOVAL_REASON_{reason.value}", lang), (reason, lang)


def test_notice_has_same_placeholders_in_every_language():
    for code in ("ORDER_NOTICE_ITEMS_REMOVED", "ORDER_NOTICE_ITEMS_REMOVED_FEE", "ORDER_NOTICE_ALL_REMOVED", "ORDER_NOTICE_CAN_CANCEL"):
        found = {lang: set(re.findall(r"\{(\w+)\}", MESSAGES[code][lang])) for lang in SUPPORTED}
        assert found["en"] == found["hi"] == found["bho"], (code, found)


def test_notice_shows_new_total_in_each_language():
    for lang in SUPPORTED:
        text = translate_fmt("ORDER_NOTICE_ITEMS_REMOVED", lang, count=2, total="280.00")
        assert "280.00" in text and "2" in text and "{" not in text


@pytest.mark.parametrize(
    "method,path",
    [("get", "/api/v1/seller/orders"), ("get", f"/api/v1/seller/orders/{uuid.uuid4()}"),
     ("post", f"/api/v1/seller/orders/{uuid.uuid4()}/accept"), ("post", f"/api/v1/seller/orders/{uuid.uuid4()}/unavailable"),
     ("post", f"/api/v1/seller/orders/{uuid.uuid4()}/reject")],
)
def test_seller_orders_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"



def test_fee_notice_shows_fee_and_total_in_each_language():
    for lang in SUPPORTED:
        text = translate_fmt("ORDER_NOTICE_ITEMS_REMOVED_FEE", lang, count=1, total="380.00", fee="30.00", free_from="799")
        assert "380.00" in text and "30.00" in text and "799" in text and "{" not in text


def test_accept_wait_message_in_all_languages():
    for lang in SUPPORTED:
        assert "2" in translate("ACCEPT_WAIT", lang)