"""Order repository (tenant-scoped). Raw order queries live here; order
CREATION (items, totals, table status, idempotency) lives in the order service
so the whole thing is one atomic transaction."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem
from app.repositories.base import TenantScopedRepository
from app.utils.errors import NotFoundError


def _order_options():
    return (
        selectinload(Order.items).selectinload(OrderItem.modifiers),
        selectinload(Order.payments),
    )


class OrderRepository(TenantScopedRepository[Order]):
    model = Order

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> Order:
        order = await self.get(restaurant_id, id)
        if order is None:
            raise NotFoundError(detail="Order not found in this restaurant.")
        return order

    async def list(
        self,
        restaurant_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Order]:
        stmt = select(self.model).options(*_order_options()).where(self.model.restaurant_id == restaurant_id)
        if branch_id is not None:
            stmt = stmt.where(self.model.branch_id == branch_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.scalars(stmt)).all())

    async def count(
        self,
        restaurant_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(self.model).where(
            self.model.restaurant_id == restaurant_id
        )
        if branch_id is not None:
            stmt = stmt.where(self.model.branch_id == branch_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        return await self.session.scalar(stmt) or 0

    async def next_order_number(self, restaurant_id: uuid.UUID) -> int:
        """Per-restaurant monotonically increasing order number."""
        from sqlalchemy import select as _select

        result = await self.session.execute(
            _select(func.max(self.model.order_number)).where(
                self.model.restaurant_id == restaurant_id
            )
        )
        return (result.scalar() or 0) + 1