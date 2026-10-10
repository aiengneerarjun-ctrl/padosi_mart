import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models import User
from app.schemas.customer import AddressCreate

GOOD = dict(receiver_name="Ravi", receiver_phone="9000000001", address_line="House 1, Patna", latitude=25.6, longitude=85.1)


def test_new_user_default_language_is_english():
    assert User.__table__.c.language.default.arg == "en"
    assert User.__table__.c.language.server_default.arg == "en"


def test_address_ok():
    assert AddressCreate(**GOOD).label == "HOME"


@pytest.mark.parametrize("bad", [{"latitude": 91}, {"longitude": -181}, {"receiver_phone": "abc"}, {"label": "GHAR"}, {"address_line": "ab"}])
def test_address_bad_input(bad):
    with pytest.raises(ValidationError):
        AddressCreate(**{**GOOD, **bad})


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/users/me/addresses"),
        ("post", "/api/v1/users/me/addresses"),
        ("put", "/api/v1/users/me/favourites/stores/00000000-0000-0000-0000-000000000000"),
        ("get", "/api/v1/users/me/favourites/products?lat=1&lng=1"),
    ],
)
def test_customer_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"