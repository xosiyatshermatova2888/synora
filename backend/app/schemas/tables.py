"""Table schemas. `version` is surfaced so the frontend can send it back on
updates — optimistic-locking protocol (Section 10)."""

import uuid

from pydantic import BaseModel, Field, ConfigDict

TABLE_STATUSES = ("AVAILABLE", "OCCUPIED", "RESERVED", "DISABLED")


class TableCreate(BaseModel):
    branch_id: uuid.UUID
    name: str = Field(min_length=1, max_length=50)
    zone: str | None = Field(default=None, max_length=50)
    capacity: int = Field(default=4, ge=1)


class TableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    zone: str | None = Field(default=None, max_length=50)
    capacity: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, pattern="^(AVAILABLE|OCCUPIED|RESERVED|DISABLED)$")
    is_active: bool | None = None


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    restaurant_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    zone: str | None
    capacity: int
    status: str
    is_active: bool
    version: int