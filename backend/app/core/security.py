"""Argon2id password hashing + JWT access tokens + token fingerprinting.

Password hashing: Argon2id (argon2-cffi) — chosen over bcrypt per master spec
Section 3. slowness/algorithm choice is explicit here so there is never a
"secure modern approach" left undefined.

Access token: short-lived JWT (HS256). Covers `sub`, `rid` (restaurant_id —
this is the source of truth for tenancy, Section 5A) and `perms` (resolved
permission codes) so `require_permission` never needs a DB round-trip.

Refresh token: OPAQUE random string (secrets.token_urlsafe). We persist only
its SHA-256 in `refresh_tokens` — never the token itself, and never JWT.
"""

import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False


def create_access_token(
    *,
    subject: str,
    restaurant_id: str,
    permission_codes: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expires = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "rid": restaurant_id,
        "perms": permission_codes,
        "typ": "access",
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT; raises JWTError on signature/expiry failure."""
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def new_refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)