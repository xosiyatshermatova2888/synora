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

import secrets
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
from app.services.subscription import start_trial
from app.utils.errors import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


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

    username = payload.username.strip().lower()
    existing = await session.scalar(select(User.id).where(User.username == username))
    if existing:
        # Generic message — never reveal that a username is taken.
        raise ConflictError(detail="Registration failed.")

    restaurant = Restaurant(
        name=payload.restaurant_name,
        slug=await _unique_slug(session, _slugify(payload.restaurant_name)),
        timezone=payload.timezone,
        currency=payload.currency,
    )
    start_trial(restaurant)  # new sign-ups get the 14-day Pro trial
    session.add(restaurant)
    await session.flush()

    session.add(Branch(restaurant_id=restaurant.id, name="Main Branch"))

    user = User(
        restaurant_id=restaurant.id,
        username=username,
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


_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    """A real Argon2 hash nobody knows the password of, built once."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(24))
    return _DUMMY_HASH


async def login(
    session: AsyncSession,
    username: str,
    password: str,
    *,
    response: Response,
    user_agent: str | None,
    ip: str | None,
) -> TokenResponsePayload:
    user = await session.scalar(
        select(User).where(User.username == username.lower(), User.deleted_at.is_(None))
    )
    # Verify against a dummy hash when the user doesn't exist, so the response
    # takes as long as for a real account (no user enumeration by timing).
    valid = verify_password(password, user.password_hash if user is not None else _dummy_hash())
    if user is None:
        valid = False
    if user is None or not valid or not user.is_active:
        raise UnauthorizedError(detail="Invalid username or password.")

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


async def list_waiter_branches(session: AsyncSession) -> list[tuple[Branch, str]]:
    """Active branches paired with their restaurant's name, for the waiter
    kiosk's pre-login branch picker. Unauthenticated — see schemas/auth.py.

    Scoped to `settings.waiter_restaurant_slug` (this deployment's own
    restaurant): the server is multi-tenant, so without that scope this would
    hand any anonymous caller every restaurant's name. Unset => empty, not
    "everyone" — fail closed.
    """
    if not settings.waiter_restaurant_slug:
        return []
    result = await session.execute(
        select(Branch, Restaurant.name)
        .join(Restaurant, Restaurant.id == Branch.restaurant_id)
        .where(
            Branch.is_active.is_(True),
            Restaurant.slug == settings.waiter_restaurant_slug,
        )
        .order_by(Restaurant.name, Branch.name)
    )
    return [(branch, restaurant_name) for branch, restaurant_name in result.all()]


async def _is_waiter_scoped_restaurant(session: AsyncSession, restaurant_id: uuid.UUID) -> bool:
    if not settings.waiter_restaurant_slug:
        return False
    slug = await session.scalar(select(Restaurant.slug).where(Restaurant.id == restaurant_id))
    return slug == settings.waiter_restaurant_slug


async def waiter_directory(session: AsyncSession, branch_id: uuid.UUID) -> list[User]:
    branch = await session.get(Branch, branch_id)
    if (
        branch is None
        or not branch.is_active
        or not await _is_waiter_scoped_restaurant(session, branch.restaurant_id)
    ):
        raise NotFoundError(detail="Branch not found.")
    result = await session.scalars(
        select(User)
        .where(
            User.restaurant_id == branch.restaurant_id,
            User.pin_hash.is_not(None),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .order_by(User.full_name)
    )
    return list(result.all())


# Permissions that disqualify an account from kiosk PIN login.
PIN_FORBIDDEN_PERMISSIONS = frozenset({"users.manage", "finance.manage", "analytics.read"})


async def pin_login(
    session: AsyncSession,
    branch_id: uuid.UUID,
    user_id: uuid.UUID,
    pin: str,
    *,
    response: Response,
    user_agent: str | None,
    ip: str | None,
) -> TokenResponsePayload:
    branch = await session.get(Branch, branch_id)
    user = await session.get(User, user_id)
    # Same dummy-check-avoidance tradeoff as login() above: only verifies
    # when a pin_hash is actually present.
    has_pin = user is not None and user.pin_hash is not None
    valid = verify_password(pin, user.pin_hash if has_pin else _dummy_hash())
    if not has_pin:
        valid = False
    # The kiosk endpoint is unauthenticated and a PIN is only 4-6 digits, so it
    # must never open a manager/owner session: those accounts use the full
    # username + password login.
    elevated = (
        user is not None
        and valid
        and bool(PIN_FORBIDDEN_PERMISSIONS & set(await _user_permissions(session, user)))
    )
    if (
        branch is None
        or user is None
        or not valid
        or elevated
        or not user.is_active
        or user.deleted_at is not None
        or user.restaurant_id != branch.restaurant_id
        or not await _is_waiter_scoped_restaurant(session, branch.restaurant_id)
    ):
        raise UnauthorizedError(detail="Invalid name or PIN.")

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


async def me(session: AsyncSession, user: User) -> UserOut:
    r = await session.get(Restaurant, user.restaurant_id)
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        restaurant_id=user.restaurant_id,
        restaurant_name=r.name if r else "",
        roles=[{"id": role.id, "name": role.name} for role in user.roles],
        permissions=await _user_permissions(session, user),
        is_platform_admin=user.is_platform_admin,
    )


@dataclass
class TokenResponsePayload:
    access_token: str
    expires_in: int
    user_id: uuid.UUID