"""Auth domain logic: register / login / refresh / logout / me.

Refresh token lifecycle (master spec Section 8):
  - access token: short-lived JWT, returned in the response body (frontend
    keeps it in memory — never localStorage).
  - refresh token: OPAQUE random string delivered ONLY as an httpOnly,
    Secure, SameSite=Strict cookie scoped to /api/v1/auth. We persist only its
    SHA-256 hash in `refresh_tokens`. Every use rotates it (old revoked, new
    issued) so replaying a stolen token revokes it instead of granting access.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Response

from app.core.config import settings
from app.core.permissions import ROLE_TEMPLATES
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    hash_password,
    new_refresh_expiry,
    verify_password,
)
from app.models.branch import Branch
from app.models.refresh_token import RefreshToken
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.auth import RegisterRequest, UserOut
from app.services.permissions import ensure_system_permissions_and_roles
from app.utils.errors import UnauthorizedError, ConflictError, ValidationError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(name: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in name)
    return "-".join(x for x in s.split("-") if x)[:80]


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug = base or "restaurant"
    existing = set(await session.scalars(select(Restaurant.slug)))
    if slug not in existing:
        return slug
    for i in range(2, 1000):
        candidate = f"{slug}-{i}"
        if candidate not in existing:
            return candidate
    return f"{slug}-{uuid.uuid4().hex[:6]}"


async def _user_permissions(session: AsyncSession, user: User) -> list[str]:
    codes: list[str] = []
    for role in user.roles:
        for p in role.permissions:
            if p.code not in codes:
                codes.append(p.code)
    return codes


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path=settings.refresh_cookie_path,
    )


async def _create_refresh_token(
    session: AsyncSession, user_id: uuid.UUID, user_agent: str | None, ip: str | None
) -> str:
    token = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=new_refresh_expiry(),
            user_agent=user_agent[:300] if user_agent else None,
            ip_address=ip,
        )
    )
    await session.flush()
    return token


async def register(
    session: AsyncSession,
    payload: RegisterRequest,
    *,
    response: Response,
    user_agent: str | None,
    ip: str | None,
) -> TokenResponsePayload:
    # Idempotent bootstrap of the global permissions/roles (Section 7A).
    roles_by_name = await ensure_system_permissions_and_roles(session)

    existing = await session.scalar(select(User.id).where(User.email == payload.email))
    if existing:
        # Generic message — never reveal that an email exists.
        raise ConflictError(detail="Registration failed.")

    restaurant = Restaurant(
        name=payload.restaurant_name,
        slug=await _unique_slug(session, _slugify(payload.restaurant_name)),
        timezone=payload.timezone,
        currency=payload.currency,
    )
    session.add(restaurant)
    await session.flush()

    session.add(Branch(restaurant_id=restaurant.id, name="Main Branch"))

    user = User(
        restaurant_id=restaurant.id,
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    # Assign the roles collection BEFORE the user is flushed so SQLAlchemy does
    # not try a synchronous lazy-load of an uninitialized collection (would
    # raise MissingGreenlet under the async engine).
    user.roles = [roles_by_name["OWNER"]]
    session.add(user)
    await session.flush()

    # The trusted owner role is granted its template permissions; deriving the
    # codes from ROLE_TEMPLATES avoids a synchronous lazy-load of the freshly
    # flushed `user.roles` collection under the async engine.
    access = create_access_token(
        subject=str(user.id),
        restaurant_id=str(restaurant.id),
        permission_codes=list(ROLE_TEMPLATES["OWNER"]),
    )
    refresh = await _create_refresh_token(session, user.id, user_agent, ip)
    await session.commit()

    _set_refresh_cookie(response, refresh)
    return TokenResponsePayload(
        access_token=access, expires_in=settings.access_token_expire_minutes * 60, user_id=user.id
    )


async def login(
    session: AsyncSession,
    email: str,
    password: str,
    *,
    response: Response,
    user_agent: str | None,
    ip: str | None,
) -> TokenResponsePayload:
    user = await session.scalar(
        select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    )
    # Verify against a dummy hash when the user doesn't exist to keep timing
    # roughly uniform regardless of account presence.
    valid = (
        verify_password(password, user.password_hash)
        if user is not None
        else False
    )
    if user is None or not valid or not user.is_active:
        raise UnauthorizedError(detail="Invalid email or password.")

    access = create_access_token(
        subject=str(user.id),
        restaurant_id=str(user.restaurant_id),
        permission_codes=await _user_permissions(session, user),
    )
    refresh = await _create_refresh_token(session, user.id, user_agent, ip)
    await session.commit()

    _set_refresh_cookie(response, refresh)
    return TokenResponsePayload(
        access_token=access, expires_in=settings.access_token_expire_minutes * 60, user_id=user.id
    )


async def refresh(
    session: AsyncSession,
    refresh_token: str,
    *,
    response: Response,
    user_agent: str | None,
    ip: str | None,
) -> TokenResponsePayload:
    record = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(refresh_token)
        )
    )
    if record is None or record.revoked_at is not None:
        raise UnauthorizedError(detail="Invalid or expired refresh token.")
    expires = record.expires_at
    # SQLite returns naive UTC datetimes; normalize so the comparison works
    # on both SQLite (tests) and PostgreSQL (tz-aware) backends.
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= _utcnow():
        raise UnauthorizedError(detail="Invalid or expired refresh token.")

    user = await session.get(User, record.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise UnauthorizedError(detail="Invalid or expired refresh token.")

    # Rotate: revoke the presented token, issue a fresh one.
    record.revoked_at = _utcnow()

    access = create_access_token(
        subject=str(user.id),
        restaurant_id=str(user.restaurant_id),
        permission_codes=await _user_permissions(session, user),
    )
    new_refresh = await _create_refresh_token(session, user.id, user_agent, ip)
    await session.commit()

    _set_refresh_cookie(response, new_refresh)
    return TokenResponsePayload(
        access_token=access, expires_in=settings.access_token_expire_minutes * 60, user_id=user.id
    )


async def logout(session: AsyncSession, refresh_token: str | None, *, response: Response) -> None:
    response.delete_cookie(
        settings.refresh_cookie_name, path=settings.refresh_cookie_path
    )
    if refresh_token:
        record = await session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh_token)
            )
        )
        if record is not None:
            record.revoked_at = _utcnow()
            await session.commit()


async def me(session: AsyncSession, user: User) -> UserOut:
    r = await session.get(Restaurant, user.restaurant_id)
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        restaurant_id=user.restaurant_id,
        restaurant_name=r.name if r else "",
        roles=[{"id": role.id, "name": role.name} for role in user.roles],
        permissions=await _user_permissions(session, user),
    )


@dataclass
class TokenResponsePayload:
    access_token: str
    expires_in: int
    user_id: uuid.UUID