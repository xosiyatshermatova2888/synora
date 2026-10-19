"""Notification domain logic — `create_notification` is the only place a
`Notification` row is written, and it's also the only place that pushes the
WebSocket event, so the durable row and the live push can never drift apart.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.utils.errors import NotFoundError
from app.websocket.manager import manager


async def create_notification(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    type_: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> Notification:
    notification = Notification(
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        type=type_,
        title=title,
        body=body,
        link=link,
    )
    session.add(notification)
    await session.flush()
    await session.commit()

    # Push only after the commit succeeds — never for a write that rolls back.
    await manager.broadcast(
        restaurant_id,
        branch_id,
        {
            "event": "notification",
            "notification": {
                "id": str(notification.id),
                "type": notification.type,
                "title": notification.title,
                "body": notification.body,
                "link": notification.link,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
            },
        },
    )
    return notification


async def list_notifications(
    session: AsyncSession, restaurant_id: uuid.UUID, *, limit: int = 30, offset: int = 0
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.restaurant_id == restaurant_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(stmt)).all())


async def mark_read(session: AsyncSession, restaurant_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    notification = await session.scalar(
        select(Notification).where(
            Notification.restaurant_id == restaurant_id, Notification.id == notification_id
        )
    )
    if notification is None:
        raise NotFoundError(detail="Notification not found in this restaurant.")
    notification.is_read = True
    await session.commit()
    return notification


async def mark_all_read(session: AsyncSession, restaurant_id: uuid.UUID) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.restaurant_id == restaurant_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await session.commit()
