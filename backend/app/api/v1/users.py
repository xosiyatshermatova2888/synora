"""Staff (team member) API — create/list users within the caller's own
restaurant, gated by `users.read` / `users.manage`. Adding OWNER/ADMIN is
intentionally not exposed here (only via /auth/register)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.users import StaffCreateRequest, StaffOut
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


def _to_out(user: User) -> StaffOut:
    return StaffOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=[r.name for r in user.roles],
        is_active=user.is_active,
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
