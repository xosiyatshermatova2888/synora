"""Audit log domain logic. `log_action` is deliberately fail-soft: a broken
audit write must never be the reason a real action (a discount, a role
change) fails, so any error here is logged and swallowed, never raised.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger("synora.audit")


async def log_action(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    summary: str,
) -> None:
    try:
        session.add(
            AuditLog(
                restaurant_id=restaurant_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                summary=summary,
            )
        )
        await session.commit()
    except Exception:
        logger.exception("Failed to write audit log entry for action=%s", action)
        await session.rollback()


async def list_audit_log(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    *,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.restaurant_id == restaurant_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())
