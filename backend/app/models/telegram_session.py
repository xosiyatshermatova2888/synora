"""Per-chat conversation state for the Telegram ordering bot.

DB-backed (not Redis/in-memory) — consistent with the rest of the app's
persistence, and bot traffic volume doesn't justify a new infra dependency.
`state` holds the step + in-progress cart as JSON; `app/services/
telegram_bot.py::handle_update` is the only place that reads or writes it.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TelegramSession(Base):
    __tablename__ = "telegram_sessions"

    # Telegram's own chat id — globally unique per bot, and each bot belongs
    # to exactly one restaurant, so this is a safe primary key.
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
