import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from app.core.i18n import MESSAGES
from app.main import app
from app.models.delivery import DeliveryStatus
from app.services import delivery_assignment as da
from app.services.delivery_rules import (
    ACTIVE_DELIVERY_STATUSES, DELIVERY_STATUSES, NEARBY_RADIUS_KM, OPEN_ORDER_STATUSES, cod_amount_due,
    order_status_when_assigned, order_status_when_released,
)


@pytest.mark.parametrize(
    "method,pay,order,expected",
    [
        ("COD", "PENDING", "DELIVERY_ASSIGNED", 250.5), ("COD", "PAID", "DELIVERY_ASSIGNED", 0.0),
        ("COD", "PENDING", "CANCELLED", 0.0), ("ONLINE", "PAID", "DELIVERY_ASSIGNED", 0.0), ("ONLINE", "PENDING", "READY_FOR_PICKUP", 0.0),
    ],
)
def test_cod_amount_due(method, pay, order, expected):
    assert cod_amount_due(method, pay, order, 250.5) == expected


def test_active_statuses_are_valid():
    assert set(ACTIVE_DELIVERY_STATUSES) <= set(DELIVERY_STATUSES)
    assert "RELEASED" not in ACTIVE_DELIVERY_STATUSES and "DELIVERED" not in ACTIVE_DELIVERY_STATUSES


def test_open_order_statuses_start_at_confirmed_and_end_at_ready():
    assert OPEN_ORDER_STATUSES[0] == "CONFIRMED" and OPEN_ORDER_STATUSES[-1] == "READY_FOR_PICKUP"
    assert "PLACED" not in OPEN_ORDER_STATUSES and "DELIVERY_ASSIGNED" not in OPEN_ORDER_STATUSES  # PLACED = abhi pakka nahi
    assert "CANCELLED" not in OPEN_ORDER_STATUSES


@pytest.mark.parametrize(
    "fn,cur,expected",
    [
        (order_status_when_assigned, "READY_FOR_PICKUP", "DELIVERY_ASSIGNED"),
        (order_status_when_assigned, "CONFIRMED", "CONFIRMED"),  # dukaan abhi tayyari me: seller ka rollup na bigde
        (order_status_when_assigned, "SELLER_ACCEPTED", "SELLER_ACCEPTED"),
        (order_status_when_assigned, "PREPARING", "PREPARING"),
        (order_status_when_released, "DELIVERY_ASSIGNED", "READY_FOR_PICKUP"),
        (order_status_when_released, "PREPARING", "PREPARING"),
        (order_status_when_released, "CONFIRMED", "CONFIRMED"),
        (order_status_when_released, "CANCELLED", "CANCELLED"),
    ],
)
def test_order_status_when_assigned_or_released(fn, cur, expected):
    assert fn(cur) == expected


def test_delivery_status_enum_matches_rules():
    assert {s.value for s in DeliveryStatus} == set(DELIVERY_STATUSES)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/delivery/orders/available"),
        ("get", "/api/v1/delivery/orders/current"),
        ("post", "/api/v1/delivery/orders/00000000-0000-0000-0000-000000000000/accept"),
        ("post", "/api/v1/delivery/orders/00000000-0000-0000-0000-000000000000/release"),
    ],
)
def test_order_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_new_error_codes_exist_in_all_languages():
    for code in ["ORDER_NOT_AVAILABLE", "PARTNER_BUSY", "PARTNER_OFFLINE", "DELIVERY_NOT_FOUND", "NO_ACTIVE_DELIVERY", "ORDER_TOO_FAR"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code


def _order():
    def item(name, qty=1):
        return NS(id=uuid.uuid4(), name=name, name_hi=None, name_bho=None, quantity=qty, selling_unit="1 kg")

    kept, gone = item("Atta", 2), item("Chini")
    ram = NS(id=uuid.uuid4(), status="READY_FOR_PICKUP", store_name="Ram Kirana", store_address="A Road",
             store_latitude=25.6000, store_longitude=85.1000, items=[kept, gone])
    shut = NS(id=uuid.uuid4(), status="REJECTED", store_name="Band Dukaan", store_address="B Road",
              store_latitude=25.7, store_longitude=85.3, items=[item("Dal")])
    sweets = NS(id=uuid.uuid4(), status="READY_FOR_PICKUP", store_name="Sharma Sweets", store_address="C Road",
                store_latitude=25.6045, store_longitude=85.1000, items=[item("Laddu")])
    return NS(
        id=uuid.uuid4(), order_number="PD1001", store_orders=[ram, shut, sweets], removals=[NS(order_item_id=gone.id)],
        latitude=25.6200, longitude=85.1000, delivery_fee=30, payment_method="COD", payment_status="PENDING",
        status="READY_FOR_PICKUP", total=630, created_at=datetime.now(timezone.utc),
        receiver_name="Ravi", receiver_phone="9800000001", address_line="House 1",
    )


def test_available_card_hides_customer_and_removed_items():
    card = da._available_card(_order(), 25.6000, 85.1000, "en")
    assert [s.store_name for s in card.stores] == ["Ram Kirana", "Sharma Sweets"]  # REJECTED dukaan nahi
    assert [i.name for i in card.stores[0].items] == ["Atta"]  # seller ne jo hataya wo nahi
    assert card.amount_due == 630.0
    assert [s.status for s in card.stores] == ["READY_FOR_PICKUP", "READY_FOR_PICKUP"]  # partner ko dikhe dukaan tayyar hai ya nahi
    dumped = card.model_dump_json()
    assert "Ravi" not in dumped and "9800000001" not in dumped and "House 1" not in dumped  # accept se pehle privacy


def test_available_card_distances():
    card = da._available_card(_order(), 25.6000, 85.1000, "en")
    assert card.pickup_distance_km == 0.0  # partner Ram Kirana ke ek dum paas
    assert 1.5 < card.drop_distance_km < 2.5  # sabse door wali dukaan (Ram Kirana, ~2.2 km) se customer


def test_only_nearby_orders_are_shown_closest_first():
    near, far = _order(), _order()
    for so in far.store_orders:
        so.store_latitude += 0.2  # ~22 km door
    near2 = _order()
    for so in near2.store_orders:
        so.store_latitude += 0.01  # ~1.1 km
    cards = [da._available_card(o, 25.6000, 85.1000, "en") for o in (far, near2, near)]
    shown = da._nearby(cards)
    assert [c.order_id for c in shown] == [near.id, near2.id]  # door wala nahi, paas wala pehle
    assert all(c.pickup_distance_km <= NEARBY_RADIUS_KM for c in shown)


def test_order_with_no_active_store_is_never_shown():
    o = _order()
    for so in o.store_orders:
        so.status = "REJECTED"
    assert da._nearby([da._available_card(o, 25.6000, 85.1000, "en")]) == []