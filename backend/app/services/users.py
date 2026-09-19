"""Staff (team member) domain logic — create/list users within a restaurant.

Mirrors the relevant slice of services/auth.py::register (role assignment,
password hashing) but never creates a Restaurant/Branch and never issues
tokens: this only adds a user to the CALLER's existing tenant.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.users import StaffCreateRequest
from app.services.permissions import ensure_system_permissions_and_roles
from app.utils.errors import ConflictError, NotFoundError, ValidationError


async def list_staff(session: AsyncSession, restaurant_id: uuid.UUID) -> list[User]:
    result = await session.scalars(
        select(User)
        .where(User.restaurant_id == restaurant_id, User.deleted_at.is_(None))
        .order_by(User.created_at)
    )
    return list(result.all())


async def create_staff(
    session: AsyncSession, restaurant_id: uuid.UUID, payload: StaffCreateRequest
) -> User:
    roles_by_name = await ensure_system_permissions_and_roles(session)
    role = roles_by_name.get(payload.role)
    if role is None:
        raise ValidationError(detail=f"Unknown role '{payload.role}'.")

    username = payload.username.strip().lower()
    existing = await session.scalar(select(User.id).where(User.username == username))
    if existing:
        raise ConflictError(detail="A user with this username already exists.")

    user = User(
        restaurant_id=restaurant_id,
        username=username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    # Assign before flush — same reasoning as auth.register: avoids a sync
    # lazy-load of an uninitialized collection under the async engine.
    user.roles = [role]
    session.add(user)
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user


async def set_pin(
    session: AsyncSession, restaurant_id: uuid.UUID, user_id: uuid.UUID, pin: str
) -> User:
    user = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.restaurant_id == restaurant_id,
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        raise NotFoundError(detail="Staff member not found.")

    user.pin_hash = hash_password(pin) if pin else None
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user


async def set_password(
    session: AsyncSession, restaurant_id: uuid.UUID, user_id: uuid.UUID, password: str
) -> User:
    user = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.restaurant_id == restaurant_id,
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        raise NotFoundError(detail="Staff member not found.")

    user.password_hash = hash_password(password)
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user
