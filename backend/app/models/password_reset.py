"""One-time password reset tokens (Phase M).

Stored as a SHA-256 hash — exactly like `refresh_tokens` — so a DB leak never
hands out usable reset links. Single-use (`used_at`), short-lived (default 45
minutes), and cadenced: confirming a reset also revokes every refresh token for
the user so a stolen session can't outlive a password change.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk


class PasswordResetToken(Base, TimestampMixin):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))