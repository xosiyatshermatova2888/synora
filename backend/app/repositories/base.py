"""Base repository + tenant-scoped repository.

This is the CONCRETE tenancy mechanism (Section 5A of the master spec).

Rule: no code path queries a tenant-scoped table without a `restaurant_id`.
`TenantScopedRepository` enforces it by making `restaurant_id` a required
argument of `get / list / update / delete / ...` and applying it as the first
WHERE clause. Inherit from it for every entity that carries a `restaurant_id`
column; never hardcode ad-hoc filtering in route handlers.

Cross-tenant access must surface as HTTP 404 — repositories raise
`NotFoundError` regardless of whether the row exists in another tenant, so
resource presence is never disclosed.
"""

import uuid
from typing import Generic, TypeVar

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.errors import NotFoundError

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def save(self, instance: ModelT) -> ModelT:
        await self.session.flush()
        return instance


class TenantScopedRepository(BaseRepository[ModelT]):
    """Repository for entities that carry a `restaurant_id` column.

    Every tenant-scoped operation requires `restaurant_id` and applies it as
    the first WHERE clause. There is intentionally no public method to query
    without it.
    """

    @staticmethod
    def _tenant_clause(restaurant_id: uuid.UUID) -> ColumnElement[bool]:
        return TenantScopedRepository.model.restaurant_id == restaurant_id

    async def get(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> ModelT | None:
        stmt = select(self.model).where(
            self.model.restaurant_id == restaurant_id, self.model.id == id
        )
        result = await self.session.scalar(stmt)
        # 404 semantics: presence is never disclosed across tenants.
        return result

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> ModelT:
        result = await self.get(restaurant_id, id)
        if result is None:
            raise NotFoundError(
                detail=f"{self.model.__name__} not found in this restaurant."
            )
        return result

    async def list(
        self,
        restaurant_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        order_by: ColumnElement | None = None,
    ) -> list[ModelT]:
        stmt = select(self.model).where(
            self.model.restaurant_id == restaurant_id
        )
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        return list(result)

    async def delete(self, restaurant_id: uuid.UUID, instance: ModelT) -> None:
        if instance.restaurant_id != restaurant_id:
            raise NotFoundError(
                detail=f"{self.model.__name__} not found in this restaurant."
            )
        await self.session.delete(instance)
        await self.session.flush()

    async def count(self, restaurant_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model).where(
            self.model.restaurant_id == restaurant_id
        )
        return await self.session.scalar(stmt) or 0