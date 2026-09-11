"""Staff (team member) schemas — create/list users within the caller's own
restaurant. Roles are restricted to the non-owner system templates; granting
OWNER/ADMIN happens only at restaurant registration (Section 8), not here.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

StaffRole = Literal["MANAGER", "CASHIER", "WAITER", "KITCHEN", "ACCOUNTANT"]


class StaffCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: StaffRole


class StaffOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    roles: list[str]
    is_active: bool
