from fastapi.testclient import TestClient

from app.core.i18n import MESSAGES, SUPPORTED, resolve_lang
from app.main import app


def test_every_message_has_all_languages():
    for code, texts in MESSAGES.items():
        for lang in SUPPORTED:
            assert texts.get(lang), f"{code} me {lang} translation missing hai"


def test_resolve_lang():
    assert resolve_lang(None) == "en"
    assert resolve_lang("bho") == "bho"
    assert resolve_lang("en-US,en;q=0.9") == "en"
    assert resolve_lang("fr,hi;q=0.5") == "hi"
    assert resolve_lang("en;q=0.2,bho;q=0.9") == "bho"
    assert resolve_lang("garbage;q=abc") == "en"


def test_error_message_follows_language_header():
    client = TestClient(app)
    for lang, expected in [("en", "Please log in."), ("hi", "कृपया लॉगिन करें।"), ("bho", "लॉगिन करीं।")]:
        r = client.get("/api/v1/users/me", headers={"Accept-Language": lang})
        assert r.status_code == 401
        detail = r.json()["detail"]
        assert detail["code"] == "NOT_AUTHENTICATED"
        assert detail["message"] == expected
        assert r.headers["content-language"] == lang


def test_validation_error_is_translated():
    client = TestClient(app)
    r = client.post("/api/v1/auth/otp/request", json={}, headers={"Accept-Language": "bho"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert r.json()["detail"]["message"] == "कुछ जानकारी सही नइखे।" 