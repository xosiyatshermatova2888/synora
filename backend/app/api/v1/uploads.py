"""File upload endpoint (Phase L / M).

Accepts image uploads for menu items (categories/products) and stores them via
`app.integrations.storage` — S3-compatible object storage (MinIO, S3, R2, ...)
when `S3_ENDPOINT` is configured, otherwise a dev fallback to local disk under
UPLOAD_DIR. The returned URL is absolute for S3 or a `/files/*` path for disk.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File

from app.api.deps import get_current_tenant, require_permission
from app.integrations.storage import save as storage_save
from app.utils.errors import ValidationError

router = APIRouter(prefix="/uploads", tags=["uploads"])

def _image_extension(data: bytes) -> str | None:
    """Extension implied by the magic bytes (None = not an accepted image)."""
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return ".avif"
    return None


def _looks_like_image(data: bytes) -> bool:
    """The Content-Type header is client-supplied; check the magic bytes too."""
    return (
        data.startswith(b"\xff\xd8\xff")  # JPEG
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or data[:6] in (b"GIF87a", b"GIF89a")
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
        or (data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"))
    )


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif", "image/gif"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    _tenant: uuid.UUID = Depends(get_current_tenant),
    _: None = Depends(require_permission("menu.update")),
):
    if file.content_type not in ALLOWED_TYPES:
        raise ValidationError(
            detail=f"Unsupported file type '{file.content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_TYPES))}"
        )

    data = await file.read()
    if len(data) > MAX_SIZE_BYTES:
        raise ValidationError(detail=f"File too large. Maximum size is {MAX_SIZE_BYTES // (1024 * 1024)} MB.")

    if not _looks_like_image(data):
        raise ValidationError(detail="The file is not a valid image.")

    # Never trust the client's file name/extension ("a.png.html"): the stored
    # name is random and its extension comes from the verified content.
    filename = f"{uuid.uuid4().hex}{_image_extension(data)}"

    url = await storage_save(data, filename)
    return {"url": url, "filename": filename}
