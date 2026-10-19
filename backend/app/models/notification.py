"""Notification domain — operational alerts pushed to staff (new order, low
stock, payment recorded, order cancelled). Written and broadcast together by
`app/services/notifications.py::create_notification`; the WebSocket push
(`app/websocket/manager.py`) and this row are two views of the same event —
the row is the durable, catch-up-on-reconnect copy, the WS push is the
live one.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, uuid_pk

NOTIFICATION_TYPES = ("NEW_ORDER", "LOW_STOCK", "PAYMENT", "ORDER_CANCELLED", "BILL_REQUEST", "SUBSCRIPTION")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
