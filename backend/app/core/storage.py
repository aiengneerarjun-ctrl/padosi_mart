"""Photo storage. Do tareeke, STORAGE_BACKEND setting se chuno:
  local = dev me, photos backend ke volume (MEDIA_DIR) me rehti hain aur /media se dikhti hain
  s3    = production me, koi bhi S3-compatible (AWS S3, Cloudflare R2, Wasabi ...). Photos API server par nahi rakhte.
"""
import asyncio
import logging
import os
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)
_client = None


class StorageError(Exception):
    """Storage se baat nahi ho paayi."""


def public_url(key: str) -> str:
    return f"{settings.media_public_url.rstrip('/')}/{key}"


def _use_s3() -> bool:
    if settings.storage_backend not in ("local", "s3"):
        raise RuntimeError("STORAGE_BACKEND 'local' ya 's3' hona chahiye")
    return settings.storage_backend == "s3"


# ---------------- local (dev) ----------------


def _local_path(key: str) -> Path:
    base = Path(settings.media_dir).resolve()
    path = (base / key).resolve()
    if base not in path.parents:  # key me ../ jaisa kuch ho to bahar likhne se roko
        raise StorageError(key)
    return path


def _local_write(key: str, data: bytes) -> None:
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)  # adhuri file kabhi dikhai nahi deti


def _local_delete(keys: list[str]) -> None:
    for key in keys:
        path = _local_path(key)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()  # photo ka folder khali ho gaya to hata do
        except OSError:
            pass


# ---------------- s3 (production) ----------------


def _s3():
    global _client
    if _client is None:
        if not settings.s3_access_key or not settings.s3_secret_key:
            raise RuntimeError("S3_ACCESS_KEY aur S3_SECRET_KEY set karo (STORAGE_BACKEND=s3 ke liye)")
        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3},
                connect_timeout=5,
                read_timeout=20,
            ),
        )
    return _client


# ---------------- public functions ----------------


async def put_object(key: str, data: bytes, content_type: str) -> None:
    if not _use_s3():
        try:
            await asyncio.to_thread(_local_write, key, data)
        except OSError as exc:
            logger.error("local storage write failed for %s: %s", key, exc)
            raise StorageError(key) from exc
        return

    from botocore.exceptions import BotoCoreError, ClientError

    try:
        await asyncio.to_thread(
            _s3().put_object,
            Bucket=settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            # Key me image ki unique id hai, isliye file badalti nahi: 1 saal tak cache theek hai
            CacheControl="public, max-age=31536000, immutable",
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("storage put failed for %s: %s", key, exc)
        raise StorageError(key) from exc


async def delete_objects(keys: list[str]) -> None:
    """Best effort: fail ho to bas log likhta hai (extra file bachi rahegi, user ko error nahi)."""
    if not keys:
        return
    try:
        if not _use_s3():
            await asyncio.to_thread(_local_delete, keys)
        else:
            await asyncio.to_thread(
                _s3().delete_objects,
                Bucket=settings.s3_bucket,
                Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("storage delete failed for %s: %s", keys, exc)