from fastapi.testclient import TestClient

from app.main import app


def test_health_route_exists():
    client = TestClient(app)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert "checks" in r.json()
