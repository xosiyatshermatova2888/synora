"""Public (unauthenticated) QR-menu domain logic — the one read/write path in
the API that resolves its tenant from a URL slug instead of a JWT claim.
Every lookup here is written to fail closed: an unknown/inactive slug, a
branch that doesn't belong to that restaurant, or a table that doesn't
belong to that branch all 404 identically, never disclosing which part was
wrong (Section 5A's cross-tenant-404 convention extended to a public route).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.branch import Branch
from app.models.menu import Category, Product
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.utils.errors import NotFoundError


async def resolve_restaurant(session: AsyncSession, restaurant_slug: str) -> Restaurant:
    restaurant = await session.scalar(
        select(Restaurant).where(Restaurant.slug == restaurant_slug, Restaurant.is_active.is_(True))
    )
    if restaurant is None:
        raise NotFoundError(detail="Menu not found.")
    return restaurant


async def resolve_branch(session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID) -> Branch:
    branch = await session.scalar(
        select(Branch).where(
            Branch.id == branch_id, Branch.restaurant_id == restaurant_id, Branch.is_active.is_(True)
        )
    )
    if branch is None:
        raise NotFoundError(detail="Branch not found.")
    return branch


async def resolve_table(session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID, table_id: uuid.UUID) -> Table:
    table = await session.scalar(
        select(Table).where(
            Table.id == table_id,
            Table.restaurant_id == restaurant_id,
            Table.branch_id == branch_id,
            Table.is_active.is_(True),
        )
    )
    if table is None:
        raise NotFoundError(detail="Table not found.")
    return table


async def get_public_menu(session: AsyncSession, restaurant_slug: str) -> dict:
    restaurant = await resolve_restaurant(session, restaurant_slug)

    branches = list(
        (
            await session.scalars(
                select(Branch)
                .where(Branch.restaurant_id == restaurant.id, Branch.is_active.is_(True))
                .order_by(Branch.name)
            )
        ).all()
    )

    categories = list(
        (
            await session.scalars(
                select(Category)
                .where(
                    Category.restaurant_id == restaurant.id,
                    Category.is_active.is_(True),
                    Category.deleted_at.is_(None),
                )
                .order_by(Category.sort_order, Category.name)
            )
        ).all()
    )

    products = list(
        (
            await session.scalars(
                select(Product)
                .options(selectinload(Product.modifier_groups))
                .where(
                    Product.restaurant_id == restaurant.id,
                    Product.is_active.is_(True),
                    Product.is_available.is_(True),
                    Product.deleted_at.is_(None),
                )
                .order_by(Product.name)
            )
        ).all()
    )
    products_by_category: dict[uuid.UUID | None, list[Product]] = {}
    for p in products:
        products_by_category.setdefault(p.category_id, []).append(p)

    return {
        "restaurant_name": restaurant.name,
        "currency": restaurant.currency,
        "branches": branches,
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "image_url": c.image_url,
                "products": products_by_category.get(c.id, []),
            }
            for c in categories
        ],
    }


async def get_public_tables(session: AsyncSession, restaurant_slug: str, branch_id: uuid.UUID) -> list[Table]:
    restaurant = await resolve_restaurant(session, restaurant_slug)
    await resolve_branch(session, restaurant.id, branch_id)
    return list(
        (
            await session.scalars(
                select(Table)
                .where(Table.restaurant_id == restaurant.id, Table.branch_id == branch_id, Table.is_active.is_(True))
                .order_by(Table.name)
            )
        ).all()
    )
