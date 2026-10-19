"""Staff (team member) API — create/list users within the caller's own
restaurant, gated by `users.read` / `users.manage`. Adding OWNER/ADMIN is
intentionally not exposed here (only via /auth/register)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user_restaurant, require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.users import (
    SetPasswordRequest,
    SetPinRequest,
    StaffActiveUpdate,
    StaffCreateRequest,
    StaffOut,
    StaffRoleUpdate,
    StaffUpdateRequest,
)
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


def _to_out(user: User) -> StaffOut:
    return StaffOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        roles=[r.name for r in user.roles],
        is_active=user.is_active,
        has_pin=user.pin_hash is not None,
    )


@router.get("", response_model=list[StaffOut])
async def list_users(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.read")),
):
    staff = await users_service.list_staff(db, current_tenant)
    return [_to_out(u) for u in staff]


@router.post("", response_model=StaffOut, status_code=201)
async def create_user(
    payload: StaffCreateRequest,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    user = await users_service.create_staff(db, current_tenant, payload)
    return _to_out(user)


@router.patch("/{user_id}/pin", response_model=StaffOut)
async def set_pin(
    user_id: uuid.UUID,
    payload: SetPinRequest,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    user = await users_service.set_pin(db, current_tenant, user_id, payload.pin)
    return _to_out(user)


@router.patch("/{user_id}/password", response_model=StaffOut)
async def set_password(
    user_id: uuid.UUID,
    payload: SetPasswordRequest,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    user = await users_service.set_password(
        db, current_tenant, user_id, payload.password, actor_user_id=current_user.id
    )
    return _to_out(user)


@router.patch("/{user_id}", response_model=StaffOut)
async def update_user(
    user_id: uuid.UUID,
    payload: StaffUpdateRequest,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    user = await users_service.update_staff(
        db, current_tenant, user_id, payload.full_name, payload.phone
    )
    return _to_out(user)


@router.patch("/{user_id}/role", response_model=StaffOut)
async def update_user_role(
    user_id: uuid.UUID,
    payload: StaffRoleUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    user = await users_service.change_role(
        db, current_tenant, user_id, payload.role, actor_user_id=current_user.id
    )
    return _to_out(user)


@router.patch("/{user_id}/active", response_model=StaffOut)
async def update_user_active(
    user_id: uuid.UUID,
    payload: StaffActiveUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    user = await users_service.set_active(
        db, current_tenant, user_id, payload.is_active, actor_user_id=current_user.id
    )
    return _to_out(user)
