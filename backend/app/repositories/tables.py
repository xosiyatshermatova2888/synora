"""Table repository. Updates are optimistic-lock-safe (Section 10): a stale
`version` fails the WHERE clause and raises ConflictError instead of silently
overwriting a concurrent change (e.g. two waiters double-booking a table)."""

import uuid

from sqlalchemy import select, update

from app.models.table import Table
from app.repositories.base import TenantScopedRepository
from app.utils.errors import ConflictError, NotFoundError


class TableRepository(TenantScopedRepository[Table]):
    model = Table

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> Table:
        table = await self.get(restaurant_id, id)
        if table is None or not table.is_active:
            raise NotFoundError(detail="Table not found in this restaurant.")
        return table

    async def list_for_branch(
        self, restaurant_id: uuid.UUID, branch_id: uuid.UUID
    ) -> list[Table]:
        stmt = (
            select(self.model)
            .where(
                self.model.restaurant_id == restaurant_id,
                self.model.branch_id == branch_id,
                self.model.is_active.is_(True),
            )
            .order_by(self.model.name)
        )
        return list((await self.session.scalars(stmt)).all())

    async def set_status(
        self, restaurant_id: uuid.UUID, table: Table, new_status: str, expected_version: int
    ) -> Table:
        """Atomic status transition guarded by optimistic locking.

        Returns the refreshed instance; raises ConflictError when another write
        won the race (stale `version`)."""
        if table.restaurant_id != restaurant_id:
            raise NotFoundError(detail="Table not found in this restaurant.")
        result = await self.session.execute(
            update(Table)
            .where(
                Table.id == table.id,
                Table.version == expected_version,
            )
            .values(status=new_status, version=Table.version + 1)
            .returning(Table)
        )
        if result.first() is None:
            raise ConflictError(detail="Table was modified by a concurrent request. Retry.")
        await self.session.flush()
        return await self.get_or_404(restaurant_id, table.id)