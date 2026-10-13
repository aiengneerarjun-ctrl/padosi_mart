import pytest
from fastapi.testclient import TestClient

from app.core.i18n import MESSAGES
from app.main import app
from app.models.order import OrderStatus
from app.services.delivery_rules import all_stores_picked_up, can_pickup_store
from app.services.seller_order import rollup_status


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["PICKED_UP", "PICKED_UP"], True),
        (["PICKED_UP", "READY_FOR_PICKUP"], False),
        (["PICKED_UP", "REJECTED"], True),  # reject hui dukaan ginti me nahi
        (["REJECTED", "CANCELLED"], False),  # koi active dukaan nahi
        ([], False),
    ],
)
def test_all_stores_picked_up(statuses, expected):
    assert all_stores_picked_up(statuses) is expected


@pytest.mark.parametrize(
    "status,expected",
    [("READY_FOR_PICKUP", True), ("PREPARING", False), ("SELLER_ACCEPTED", False), ("PLACED", False), ("PICKED_UP", False)],
)
def test_pickup_only_when_shop_is_ready(status, expected):
    assert can_pickup_store(status) is expected


def test_seller_rollup_counts_picked_up_shop_as_ready_or_beyond():
    assert rollup_status(["PICKED_UP", "PREPARING"]) == OrderStatus.PREPARING  # baaki dukaan abhi tayyari me
    assert rollup_status(["PICKED_UP", "READY_FOR_PICKUP"]) == OrderStatus.READY_FOR_PICKUP
    assert rollup_status(["PICKED_UP", "REJECTED"]) == OrderStatus.READY_FOR_PICKUP


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/delivery/orders/00000000-0000-0000-0000-000000000000/stores/00000000-0000-0000-0000-000000000001/pickup",
        "/api/v1/delivery/orders/00000000-0000-0000-0000-000000000000/start",
    ],
)
def test_progress_routes_need_login(path):
    r = TestClient(app).post(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_new_error_codes_exist_in_all_languages():
    for code in ["STORE_NOT_READY", "STORE_PART_NOT_FOUND", "ALREADY_PICKED_UP", "NOT_ALL_PICKED_UP", "PARTNER_HAS_GOODS", "PARTNER_ON_DELIVERY"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code