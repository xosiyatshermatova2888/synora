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

    filename = f"{uuid.uuid4().hex}{Path(file.filename or 'upload').suffix.lower() or '.bin'}"

    url = await storage_save(data, filename)
    return {"url": url, "filename": filename}
