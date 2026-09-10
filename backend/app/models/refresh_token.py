import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk


class RefreshToken(Base, TimestampMixin):
    """Persisted, revocable, rotating refresh tokens.

    We store a SHA-256 hash of the token, not the token itself — a DB leak must
    not hand out active sessions. Rotation (issue new, revoke old) happens in
    `app/services/auth.py`; `/auth/logout` and "log out all devices" actually
    work because revocation is real.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip_address: Mapped[str | None] = mapped_column(String(45))