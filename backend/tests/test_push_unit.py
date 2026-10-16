import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app
from app.schemas.notification import DeviceIn
from app.services.push import ERROR, INVALID_TOKEN, OK, FcmClient, build_message, classify_response

TOKEN = "fcm-token-" + "x" * 40


@pytest.mark.parametrize("method,path", [("post", "/api/v1/notifications/devices"), ("post", "/api/v1/notifications/devices/unregister")])
def test_device_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path, json={"token": TOKEN, "platform": "android"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_device_schema_rules():
    assert DeviceIn(token=f"  {TOKEN}  ").token == TOKEN  # aas-paas ki jagah hat jati hai
    assert DeviceIn(token=TOKEN).platform == "android"
    for bad in ({"token": "short"}, {"token": "a" * 30 + " " + "b" * 30}, {"token": "a" * 2000}, {"token": TOKEN, "platform": "windows"}):
        with pytest.raises(ValidationError):
            DeviceIn(**bad)


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (200, "{}", OK),
        (404, '{"error":{"status":"NOT_FOUND","details":[{"errorCode":"UNREGISTERED"}]}}', INVALID_TOKEN),
        (400, '{"error":{"message":"The registration token is not a valid FCM registration token"}}', INVALID_TOKEN),
        (403, '{"error":{"details":[{"errorCode":"SENDER_ID_MISMATCH"}]}}', INVALID_TOKEN),
        (400, '{"error":{"message":"Invalid JSON payload"}}', ERROR),  # galti hamari: token mat hatao
        (401, "unauthenticated", ERROR),
        (429, "quota", ERROR),
        (503, "unavailable", ERROR),
    ],
)
def test_classify_response(status, body, expected):
    assert classify_response(status, body) == expected


def test_build_message_data_is_all_strings():
    m = build_message(TOKEN, "T", "B", {"code": "X", "n": 5})["message"]
    assert m["token"] == TOKEN and m["notification"] == {"title": "T", "body": "B"}
    assert all(isinstance(v, str) for v in m["data"].values()) and m["data"]["n"] == "5"


def _client(handler):
    return FcmClient(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)), project_id="demo", token_provider=lambda: "access-123")


def test_send_posts_to_fcm_v1_with_bearer():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], request.content
        return httpx.Response(200, json={"name": "projects/demo/messages/1"})

    assert asyncio.run(_client(handler).send(TOKEN, "T", "B", {"code": "X"})) == OK
    assert seen["url"] == "https://fcm.googleapis.com/v1/projects/demo/messages:send"
    assert seen["auth"] == "Bearer access-123" and TOKEN.encode() in seen["body"]


def test_send_reports_dead_token_and_survives_network_error():
    assert asyncio.run(_client(lambda r: httpx.Response(404, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}})).send(TOKEN, "T", "B", {})) == INVALID_TOKEN

    def boom(request):
        raise httpx.ConnectError("down")

    assert asyncio.run(_client(boom).send(TOKEN, "T", "B", {})) == ERROR  # push chhooti, crash nahi


def test_push_disabled_by_default_and_when_file_missing(tmp_path):
    base = dict(postgres_user="u", postgres_password="p", postgres_db="d", jwt_secret="s")
    assert Settings(_env_file=None, **base).push_enabled is False
    assert Settings(_env_file=None, fcm_service_account_file=str(tmp_path / "nahi.json"), **base).push_enabled is False
    f = tmp_path / "sa.json"
    f.write_text("{}")
    assert Settings(_env_file=None, fcm_service_account_file=str(f), **base).push_enabled is True
