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
from app.utils.errors import ConflictError, ValidationError


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

    email = str(payload.email).lower()
    existing = await session.scalar(select(User.id).where(User.email == email))
    if existing:
        raise ConflictError(detail="A user with this email already exists.")

    user = User(
        restaurant_id=restaurant_id,
        email=email,
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
