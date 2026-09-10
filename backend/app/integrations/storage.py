"""S3-compatible object storage for uploads (Phase M).

Replaces the local-disk `UPLOAD_DIR` backend with an S3 client (works against
real AWS S3, DigitalOcean Spaces, Cloudflare R2, or self-hosted MinIO). When the
S3 vars are unset the module falls back to local disk so plain local dev keeps
working without an object store — but the Docker stacks ship with MinIO wired,
so the exercised path is always S3.

boto3 is synchronous, so every network call runs via `asyncio.to_thread` to
avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from app.core.config import settings

_FILE_SAFE = re.compile(r"[^a-zA-Z0-9._-]")


def _client():
    import boto3
    from botocore.config import Config

    kwargs = {}
    if settings.s3_endpoint:
        kwargs["endpoint_url"] = settings.s3_endpoint
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"} if settings.s3_use_path_style else None,
        ),
        **kwargs,
    )


async def save(data: bytes, filename: str) -> str:
    """Store bytes and return a public URL."""
    safe = _FILE_SAFE.sub("_", filename)
    if settings.s3_endpoint:
        return await _upload_to_s3(data, safe)
    return _save_local(data, safe)


async def _upload_to_s3(data: bytes, key: str) -> str:
    await asyncio.to_thread(
        _client().put_object,
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=_guess_type(key),
    )
    base = (settings.s3_public_url_base or settings.s3_endpoint).rstrip("/")
    return f"{base}/{settings.s3_bucket}/{key}"


def _save_local(data: bytes, filename: str) -> str:
    target = Path(settings.upload_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / filename).write_bytes(data)
    return f"/files/{filename}"


def _guess_type(filename: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".avif": "image/avif",
        ".gif": "image/gif",
    }.get(Path(filename).suffix.lower(), "application/octet-stream")