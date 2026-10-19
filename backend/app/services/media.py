"""Load a stored product image as bytes (to upload it to Telegram).

`Product.image_url` is either a same-origin path served by this deployment
(`/uploads/<bucket>/<key>` -> MinIO, `/files/<name>` -> local disk) or a legacy
absolute MinIO URL. Telegram can't reach a private/LAN address to fetch a photo
itself, so the backend reads the bytes and uploads them.

Only this deployment's own storage is ever read: an arbitrary absolute URL
saved by an API client would otherwise turn the server into an SSRF proxy that
forwards internal content to a customer chat.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger("synora.media")

MAX_IMAGE_BYTES = 8 * 1024 * 1024
_TIMEOUT = httpx.Timeout(10.0)


def _storage_url(image_url: str) -> str | None:
    endpoint = settings.s3_endpoint.rstrip("/")
    if image_url.startswith("/uploads/") and endpoint:
        return endpoint + image_url[len("/uploads"):]
    if image_url.startswith(("http://", "https://")):
        parsed = urlparse(image_url)
        allowed_bases = [b.rstrip("/") for b in (settings.s3_public_url_base, settings.s3_endpoint) if b.startswith("http")]
        legacy_local = parsed.netloc in ("localhost:9000", "127.0.0.1:9000")
        if endpoint and (legacy_local or any(image_url.startswith(base + "/") for base in allowed_bases)):
            return endpoint + parsed.path
    return None


def normalize_card_photo(data: bytes, filename: str) -> tuple[bytes, str]:
    """Center-crop to 4:3 and cap the width, so every product photo in the chat
    has the same shape (restaurant photos arrive in all sizes). Falls back to
    the original bytes if the image can't be processed."""
    try:
        from io import BytesIO

        from PIL import Image, ImageOps

        # Only decode the formats we accept: Pillow can open dozens of exotic
        # ones (PSD, FITS, PDF...) that have had memory-safety bugs.
        with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP", "GIF"]) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            fitted = ImageOps.fit(img, (1024, 768), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            out = BytesIO()
            fitted.save(out, format="JPEG", quality=86, optimize=True)
        return out.getvalue(), Path(filename).stem + ".jpg"
    except Exception:  # noqa: BLE001
        return data, filename


async def load_image_bytes(image_url: str) -> tuple[bytes, str] | None:
    """Returns (bytes, filename) or None when the image can't be loaded."""
    try:
        if image_url.startswith("/files/"):
            root = Path(settings.upload_dir).resolve()
            target = (root / image_url[len("/files/"):]).resolve()
            if root not in target.parents or not target.is_file():
                return None
            data = target.read_bytes()
            return normalize_card_photo(data, target.name) if len(data) <= MAX_IMAGE_BYTES else None

        url = _storage_url(image_url)
        if url is None:
            return None
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False) as client:
            response = await client.get(url)
        if response.status_code != 200 or not response.headers.get("content-type", "").startswith("image/"):
            return None
        if len(response.content) > MAX_IMAGE_BYTES:
            return None
        return normalize_card_photo(response.content, Path(urlparse(url).path).name or "photo.jpg")
    except Exception:  # noqa: BLE001 — a missing image must never break the menu
        logger.warning("could not load image %s", image_url)
        return None
