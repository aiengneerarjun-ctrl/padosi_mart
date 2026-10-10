import asyncio

import pytest

from app.core import storage
from app.core.config import settings


@pytest.fixture()
def media(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    return tmp_path


def test_put_then_delete_removes_file_and_empty_folder(media):
    asyncio.run(storage.put_object("products/p1/i1/thumb.webp", b"abc", "image/webp"))
    f = media / "products/p1/i1/thumb.webp"
    assert f.read_bytes() == b"abc"
    asyncio.run(storage.delete_objects(["products/p1/i1/thumb.webp"]))
    assert not f.exists() and not f.parent.exists()


def test_key_cannot_escape_media_folder(media):
    with pytest.raises(storage.StorageError):
        asyncio.run(storage.put_object("../evil.txt", b"x", "text/plain"))
    assert not (media.parent / "evil.txt").exists()


def test_delete_missing_file_is_silent(media):
    asyncio.run(storage.delete_objects(["products/none/none/thumb.webp"]))


def test_public_url(monkeypatch):
    monkeypatch.setattr(settings, "media_public_url", "http://localhost:8000/media/")
    assert storage.public_url("a/b.webp") == "http://localhost:8000/media/a/b.webp"