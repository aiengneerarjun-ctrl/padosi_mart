import asyncio
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps import require_super_admin
from app.api.v1 import admin_delivery
from app.core import storage
from app.core.config import settings
from app.core.i18n import MESSAGES
from app.main import app
from app.services.delivery_rules import TRANSITIONS, can_move, normalize_vehicle_number
from app.services.image_processing import ImageError, process_document_image


def _img(size=(800, 600), fmt="JPEG", mode="RGB"):
    buf = BytesIO()
    Image.new(mode, size, (200, 100, 50) if mode == "RGB" else None).save(buf, format=fmt)
    return buf.getvalue()


# ---------- gaadi ka number ----------
@pytest.mark.parametrize(
    "raw,expected",
    [("br 01-ab 1234", "BR01AB1234"), ("BR01AB1234", "BR01AB1234"), ("  up.32 xy 9999 ", "UP32XY9999"), (None, None), ("   ", None)],
)
def test_vehicle_number_is_cleaned(raw, expected):
    assert normalize_vehicle_number(raw) == expected


@pytest.mark.parametrize("raw", ["AB12", "BR01AB1234567890", "BR01@B1234", "!!!!!!!!"])
def test_bad_vehicle_number_rejected(raw):
    with pytest.raises(ValueError):
        normalize_vehicle_number(raw)


# ---------- admin ke status badlav ----------
@pytest.mark.parametrize(
    "action,cur,ok",
    [
        ("approve", "PENDING", True), ("approve", "ACTIVE", False), ("approve", "REJECTED", False), ("approve", "SUSPENDED", False),
        ("reject", "PENDING", True), ("reject", "ACTIVE", False), ("reject", "SUSPENDED", False),
        ("suspend", "ACTIVE", True), ("suspend", "PENDING", False), ("suspend", "SUSPENDED", False), ("suspend", "REJECTED", False),
        ("reactivate", "SUSPENDED", True), ("reactivate", "ACTIVE", False), ("reactivate", "PENDING", False),
        ("delete", "PENDING", False),
    ],
)
def test_transitions(action, cur, ok):
    assert can_move(action, cur) is ok


def test_every_transition_target_is_a_valid_status():
    assert {to for _, to in TRANSITIONS.values()} <= {"PENDING", "ACTIVE", "REJECTED", "SUSPENDED"}


# ---------- ID photo ----------
def test_document_photo_becomes_webp_and_keeps_ratio():
    out = process_document_image(_img((800, 600)))
    img = Image.open(BytesIO(out))
    assert img.format == "WEBP" and img.size == (800, 600)  # square nahi banaya, crop nahi kiya


def test_big_document_photo_is_shrunk():
    out = process_document_image(_img((3200, 2000)))
    assert max(Image.open(BytesIO(out)).size) == 1600


def test_png_with_transparency_is_flattened():
    out = process_document_image(_img((600, 600), fmt="PNG", mode="RGBA"))
    assert Image.open(BytesIO(out)).mode == "RGB"


@pytest.mark.parametrize(
    "data,code",
    [(_img((300, 300)), "IMAGE_TOO_SMALL"), (_img((600, 600), fmt="GIF", mode="RGB"), "IMAGE_FORMAT_NOT_ALLOWED"), (b"not an image", "IMAGE_INVALID")],
)
def test_bad_document_photo_rejected(data, code):
    with pytest.raises(ImageError) as exc:
        process_document_image(data)
    assert exc.value.code == code


# ---------- private storage ----------
@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    public, private = tmp_path / "public", tmp_path / "private"
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "media_dir", str(public))
    monkeypatch.setattr(settings, "private_media_dir", str(private))
    return public, private


def test_private_put_get_delete(dirs):
    _, private = dirs
    key = "delivery-kyc/p1/id-1.webp"
    asyncio.run(storage.put_private_object(key, b"secret", "image/webp"))
    assert (private / key).read_bytes() == b"secret"
    assert asyncio.run(storage.get_private_object(key)) == b"secret"
    asyncio.run(storage.delete_private_objects([key]))
    assert not (private / key).exists()


def test_private_file_is_never_in_public_media_folder(dirs):
    public, private = dirs
    asyncio.run(storage.put_private_object("delivery-kyc/p1/id-1.webp", b"secret", "image/webp"))
    assert not public.exists() or not any(public.rglob("*.webp"))  # /media sirf public folder dikhata hai


def test_private_missing_file_raises_not_found(dirs):
    with pytest.raises(storage.StorageNotFound):
        asyncio.run(storage.get_private_object("delivery-kyc/none/none.webp"))


def test_private_key_cannot_escape_folder(dirs):
    _, private = dirs
    with pytest.raises(storage.StorageError):
        asyncio.run(storage.put_private_object("../evil.webp", b"x", "image/webp"))
    with pytest.raises(storage.StorageError):
        asyncio.run(storage.get_private_object("../../etc/passwd"))


# ---------- routes aur permission ----------
def test_admin_delivery_router_is_super_admin_only():
    assert any(d.dependency is require_super_admin for d in admin_delivery.router.dependencies)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/delivery/me"),
        ("post", "/api/v1/delivery/me/online"),
        ("post", "/api/v1/delivery/me/offline"),
        ("get", "/api/v1/admin/delivery-partners"),
        ("get", "/api/v1/admin/delivery-partners/00000000-0000-0000-0000-000000000000/photos/id"),
    ],
)
def test_routes_need_login(method, path):
    r = getattr(TestClient(app), method)(path)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "NOT_AUTHENTICATED"


def test_new_error_codes_exist_in_all_languages():
    for code in ["PARTNER_EXISTS", "NOT_A_PARTNER", "PARTNER_NOT_FOUND", "PARTNER_NOT_ACTIVE",
                 "PARTNER_PHOTO_NOT_FOUND", "VEHICLE_NUMBER_REQUIRED", "VEHICLE_NUMBER_INVALID"]:
        assert all(MESSAGES[code].get(lang) for lang in ("en", "hi", "bho")), code