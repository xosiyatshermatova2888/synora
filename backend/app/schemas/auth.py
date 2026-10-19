"""Auth/register payloads. Money is not involved here; decimal rules start
with menu/order schemas (Phases E+)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

UZ_TIMES = "Asia/Tashkent"
# A free-form login, not an email address — see models/user.py::User.username.
Username = Field(min_length=3, max_length=100)


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    username: str = Username
    password: str = Field(min_length=8, max_length=128)
    restaurant_name: str = Field(min_length=2, max_length=150)
    currency: str = Field(default="UZS", pattern=r"^[A-Z]{3}$")
    timezone: str = Field(default=UZ_TIMES, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds


class PermissionOut(BaseModel):
    code: str


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    restaurant_id: uuid.UUID
    restaurant_name: str
    roles: list[RoleOut]
    permissions: list[str]
    is_platform_admin: bool = False


# --- Waiter kiosk PIN login --------------------------------------------------
# Unauthenticated by design (see api/v1/auth.py): a waiter device selects a
# branch, then a name, then enters a PIN. Only names, restaurant names and a
# branch id are exposed pre-auth — no more than a restaurant's own signage.


class WaiterBranchOut(BaseModel):
    id: uuid.UUID
    name: str
    restaurant_name: str


class WaiterDirectoryEntry(BaseModel):
    id: uuid.UUID
    full_name: str


class PinLoginRequest(BaseModel):
    branch_id: uuid.UUID
    user_id: uuid.UUID
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")