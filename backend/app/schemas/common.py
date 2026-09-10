"""Pagination (Section 18): every list endpoint supports limit/offset with sane
defaults (default 20, max 100)."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


def clamp_pagination(limit: int, offset: int) -> tuple[int, int]:
    return (max(1, min(limit, 100)), max(0, offset))