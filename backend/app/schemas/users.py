"""Staff (team member) schemas — create/list users within the caller's own
restaurant. Roles are restricted to the non-owner system templates; granting
OWNER/ADMIN happens only at restaurant registration (Section 8), not here.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

StaffRole = Literal["MANAGER", "CASHIER", "WAITER", "KITCHEN", "ACCOUNTANT"]


class StaffCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: StaffRole


class StaffOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    roles: list[str]
    is_active: bool
    has_pin: bool


class SetPinRequest(BaseModel):
    """Set/replace a staff member's waiter-kiosk PIN. An empty string clears
    it (removes them from the waiter directory, disables PIN login)."""

    pin: str = Field(default="", pattern=r"^(\d{4,6})?$")


class SetPasswordRequest(BaseModel):
    """Admin resets a staff member's login password directly — there is no
    self-service "forgot password" (no email to send a reset link to)."""

    password: str = Field(min_length=8, max_length=128)
