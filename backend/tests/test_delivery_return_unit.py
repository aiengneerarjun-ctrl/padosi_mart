import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.i18n import MESSAGES
from app.main import app
from app.schemas.delivery_return import AdminReceiveBody, ReceiveBody
from app.services.delivery_rules import RETURN_STATUSES, should_restock, stock_to_return

ZERO = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    "store_type,ok,expected",
    [
        ("KIRANA", True, True),
        ("KIRANA", False, False),  # saaman kharab: stock nahi judta
        ("RESTAURANT", True, False),  # bana hua khana dobara nahi bikta
        ("RESTAURANT", False, False),
    ],
)
def test_should_restock(store_type, ok, expected):
    assert should_restock(store_type, ok) is expected


def test_stock_to_return_skips_removed_and_adds_same_product():
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    i1, i2, i3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    items = [(i1, p1, 2), (i2, p2, 3), (i3, p1, 4)]
    assert stock_to_return(items, {i2}) == {p1: 6}  # i2 pehle hi hat chuka tha
    assert stock_to_return(items, set()) == {p1: 6, p2: 3}
    assert stock_to_return([], set()) == {}


def test_return_statuses():
    assert RETURN_STATUSES == ("PENDING", "RECEIVED")


def test_receive_bodies():
    assert ReceiveBody().stock_ok is True
    assert ReceiveBody(note="  ").note is None
    assert AdminReceiveBody(note="seller jawab nahi de raha").stock_ok is True
    with pytest.raises(ValidationError):
        AdminReceiveBody(note="ab")  # admin ko karan zaroori (kam se kam 3 akshar)
    with pytest.raises(ValidationError):
        AdminReceiveBody()


def test_message_exists_in_all_languages():
    assert set(MESSAGES["RETURN_NOT_FOUND"]) == {"en", "hi", "bho"}


@pytest.mark.parametrize(
    "method,url",
    [
        ("get", "/api/v1/seller/returns"),
        ("post", f"/api/v1/seller/returns/{ZERO}/received"),
        ("get", "/api/v1/admin/returns"),
        ("post", f"/api/v1/admin/returns/{ZERO}/received"),
    ],
)
def test_routes_need_login(method, url):
    client = TestClient(app)
    r = getattr(client, method)(url, **({"json": {"note": "abc"}} if method == "post" else {}))
    assert r.status_code == 401