"""Auth/register payloads. Money is not involved here; decimal rules start
with menu/order schemas (Phases E+)."""

import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

UZ_TIMES = "Asia/Tashkent"


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    restaurant_name: str = Field(min_length=2, max_length=150)
    currency: str = Field(default="UZS", pattern=r"^[A-Z]{3}$")
    timezone: str = Field(default=UZ_TIMES, max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
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
    email: EmailStr
    full_name: str
    restaurant_id: uuid.UUID
    restaurant_name: str
    roles: list[RoleOut]
    permissions: list[str]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)