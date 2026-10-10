import pytest

from app.services.discovery import estimate_eta


def test_eta_grows_with_distance():
    assert estimate_eta("KIRANA", 0) == 8
    assert estimate_eta("KIRANA", 2.0) == 16  # 8 + 2km * 4 min
    assert estimate_eta("KIRANA", 2.1) == 17  # upar ki taraf round


def test_restaurant_takes_longer_to_prepare():
    assert estimate_eta("RESTAURANT", 1.0) > estimate_eta("KIRANA", 1.0)


def test_unknown_store_type_gets_default_prep():
    assert estimate_eta("OTHER", 0) == 10


@pytest.mark.parametrize("lat,lng", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_bad_coordinates_rejected(lat, lng):
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).get("/api/v1/shop/stores", params={"lat": lat, "lng": lng})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "VALIDATION_ERROR"