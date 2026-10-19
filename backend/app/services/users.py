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


async def _get_staff_or_404(session: AsyncSession, restaurant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).where(
            User.id == user_id,
            User.restaurant_id == restaurant_id,
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        raise NotFoundError(detail="Staff member not found.")
    return user


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
    user = await _get_staff_or_404(session, restaurant_id, user_id)
    user.pin_hash = hash_password(pin) if pin else None
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user


async def set_password(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID,
    password: str,
    actor_user_id: uuid.UUID | None = None,
) -> User:
    user = await _get_staff_or_404(session, restaurant_id, user_id)
    user.password_hash = hash_password(password)
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])

    from app.services import audit as audit_service

    await audit_service.log_action(
        session, restaurant_id, actor_user_id, "staff.password_reset", "user", user.id,
        f"Password reset for {user.username}",
    )
    return user


async def update_staff(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID,
    full_name: str | None,
    phone: str | None,
) -> User:
    user = await _get_staff_or_404(session, restaurant_id, user_id)
    if full_name is not None:
        user.full_name = full_name
    if phone is not None:
        user.phone = phone
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])
    return user


async def change_role(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID,
    role_name: str,
    actor_user_id: uuid.UUID | None = None,
) -> User:
    user = await _get_staff_or_404(session, restaurant_id, user_id)
    roles_by_name = await ensure_system_permissions_and_roles(session)
    role = roles_by_name.get(role_name)
    if role is None:
        raise ValidationError(detail=f"Unknown role '{role_name}'.")
    old_roles = ", ".join(r.name for r in user.roles) or "none"
    user.roles = [role]
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])

    from app.services import audit as audit_service

    await audit_service.log_action(
        session, restaurant_id, actor_user_id, "staff.role_change", "user", user.id,
        f"Changed {user.username}'s role from {old_roles} to {role_name}",
    )
    return user


async def set_active(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID,
    is_active: bool,
    actor_user_id: uuid.UUID | None = None,
) -> User:
    user = await _get_staff_or_404(session, restaurant_id, user_id)
    user.is_active = is_active
    await session.commit()
    await session.refresh(user, attribute_names=["roles"])

    from app.services import audit as audit_service

    action = "staff.activate" if is_active else "staff.deactivate"
    await audit_service.log_action(
        session, restaurant_id, actor_user_id, action, "user", user.id,
        f"{'Activated' if is_active else 'Deactivated'} {user.username}",
    )
    return user
