"""Audit log API — gated by `users.manage` (owner-level bar, same as
Branches/Settings: this is sensitive operational history)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_permission
from app.database.session import get_db
from app.schemas.audit import AuditLogOut
from app.services import audit as audit_service

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_log(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await audit_service.list_audit_log(db, current_tenant, action=action, limit=limit, offset=offset)
