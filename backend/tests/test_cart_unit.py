import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.cart import MAX_STORE_GAP_KM
from app.schemas.cart import CartItemSet
from app.services.cart import km_between


def test_km_between_known_distances():
    assert km_between(25.6, 85.1, 25.6, 85.1) == 0
    # 0.01 degree latitude = ~1.11 km
    assert 1.10 < km_between(25.60, 85.1, 25.61, 85.1) < 1.12
    assert km_between(25.6, 85.1, 25.605, 85.1) < MAX_STORE_GAP_KM  # ~0.55 km: allowed
    assert km_between(25.6, 85.1, 25.62, 85.1) > MAX_STORE_GAP_KM  # ~2.2 km: not allowed


@pytest.mark.parametrize("bad", [{"quantity": 0}, {"quantity": 21}, {"lat": 91}, {"lng": 181}])
def test_cart_item_bad_input(bad):
    with pytest.raises(ValidationError):
        CartItemSet(**{"quantity": 1, "lat": 25.6, "lng": 85.1, **bad})


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/cart?lat=1&lng=1"),
        ("put", "/api/v1/cart/items/00000000-0000-0000-0000-000000000000"),
        ("delete", "/api/v1/cart"),
    ],
)
def test_cart_needs_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"