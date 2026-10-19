"""Ownership checks for ids a client sends in a request body.

`restaurant_id` always comes from the JWT, but a body can also carry ids of OTHER
rows (a branch, a category...). Without a check a tenant could attach its own
records to another tenant's branch/category: block that tenant's cash-shift
slot, consume its order numbers, or wedge its data into its menu. The answer is
the same as for a missing row — 404 — so ids of other tenants are not an oracle.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.menu import Category
from app.utils.errors import NotFoundError


async def require_branch(session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID) -> None:
    found = await session.scalar(
        select(Branch.id).where(Branch.id == branch_id, Branch.restaurant_id == restaurant_id)
    )
    if found is None:
        raise NotFoundError(detail="Branch not found in this restaurant.")


async def require_category(
    session: AsyncSession, restaurant_id: uuid.UUID, category_id: uuid.UUID | None
) -> None:
    if category_id is None:
        return
    found = await session.scalar(
        select(Category.id).where(Category.id == category_id, Category.restaurant_id == restaurant_id)
    )
    if found is None:
        raise NotFoundError(detail="Category not found in this restaurant.")
