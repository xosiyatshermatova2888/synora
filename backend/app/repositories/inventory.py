import uuid

from sqlalchemy import select

from app.models.inventory import InventoryItem, InventoryTransaction
from app.repositories.base import TenantScopedRepository


class InventoryItemRepository(TenantScopedRepository[InventoryItem]):
    model = InventoryItem

    async def list_for_branch(
        self, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None = None
    ) -> list[InventoryItem]:
        stmt = select(InventoryItem).where(
            InventoryItem.restaurant_id == restaurant_id,
            InventoryItem.is_active.is_(True),
        )
        if branch_id is not None:
            stmt = stmt.where(InventoryItem.branch_id == branch_id)
        stmt = stmt.order_by(InventoryItem.name)
        return list((await self.session.scalars(stmt)).all())


class InventoryTransactionRepository(TenantScopedRepository[InventoryTransaction]):
    model = InventoryTransaction

    async def list_for_item(
        self, restaurant_id: uuid.UUID, inventory_item_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[InventoryTransaction]:
        stmt = (
            select(InventoryTransaction)
            .where(
                InventoryTransaction.restaurant_id == restaurant_id,
                InventoryTransaction.inventory_item_id == inventory_item_id,
            )
            .order_by(InventoryTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.scalars(stmt)).all())
