"""Password reset flow (Phase M): request -> email -> confirm.

Security model mirrors the refresh-token design:
  - the token we send by email is OPAQUE and stored ONLY as a SHA-256 hash
    (`app/models/password_reset.py`) — a DB leak can't be replayed.
  - single use (`used_at`) and short expiry (`settings.password_reset_expire_minutes`).
  - `/request` never reveals whether an address exists (always responds 202).
  - confirming a reset revokes EVERY refresh token for the user so a stolen
    session cannot survive a password change.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.integrations.email import build_reset_url, send_email
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.utils.errors import UnauthorizedError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _reset_eligible_user(session: AsyncSession, email: str) -> User | None:
    return session.scalar(
        select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    )


def build_reset_email_html(reset_url: str) -> str:
    return (
        "<div style='font-family:Arial,sans-serif;max-width:480px;margin:0 auto'>"
        "<h2>SYNORA — password reset</h2>"
        "<p>We received a request to reset your SYNORA password.</p>"
        "<p><a href='%s' style='display:inline-block;padding:12px 20px;"
        "background:#000;color:#fff;border-radius:8px;text-decoration:none'>"
        "Reset my password</a></p>"
        "<p>This link expires in %d minutes and can be used once. If you didn't "
        "request this, you can safely ignore this email.</p>"
        "</div>" % (reset_url, settings.password_reset_expire_minutes)
    )


async def request_reset(session: AsyncSession, email: str) -> None:
    """Issue a reset token and (try to) email it. Never errors on unknown email."""
    user = await _reset_eligible_user(session, email)
    if user is None:
        # Same 202 path regardless — no account existence disclosure.
        return

    token = secrets.token_urlsafe(48)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=_utcnow() + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    await session.commit()

    url = build_reset_url(token)
    await send_email(str(user.email), "Reset your SYNORA password", build_reset_email_html(url))


async def confirm_reset(session: AsyncSession, token: str, new_password: str) -> None:
    record = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token))
    )
    if record is None or record.used_at is not None:
        raise UnauthorizedError(detail="Invalid or expired reset token.")
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= _utcnow():
        raise UnauthorizedError(detail="Invalid or expired reset token.")

    user = await session.get(User, record.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise UnauthorizedError(detail="Invalid or expired reset token.")

    record.used_at = _utcnow()
    user.password_hash = hash_password(new_password)

    # Revoke every session the user had — a password change is a security event.
    from sqlalchemy import update

    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )
    await session.commit()


def make_reset_token(user_id: uuid.UUID) -> tuple[str, str]:
    """Test/console helper: returns (plaintext, hash) pair."""
    token = secrets.token_urlsafe(48)
    return token, _hash_token(token)