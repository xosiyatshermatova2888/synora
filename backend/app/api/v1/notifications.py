"""Notification center API — gated by `orders.read` (broad enough to cover
Manager/Cashier/Waiter/Kitchen, matching who'd care about these events)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_permission
from app.database.session import get_db
from app.schemas.notifications import NotificationOut
from app.services import notifications as notifications_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await notifications_service.list_notifications(db, current_tenant, limit=limit, offset=offset)


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    return await notifications_service.mark_read(db, current_tenant, notification_id)


@router.post("/mark-all-read", status_code=204)
async def mark_all_notifications_read(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    await notifications_service.mark_all_read(db, current_tenant)
