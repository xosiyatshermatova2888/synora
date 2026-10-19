"""Inventory ledger logic — the only place `InventoryItem.quantity` is written.

Every stock change goes through `record_transaction`, which applies the delta
and inserts the matching `InventoryTransaction` row atomically, so the running
balance and its history can never drift apart.
"""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem, InventoryTransaction
from app.repositories.inventory import InventoryItemRepository
from app.utils.errors import BusinessRuleError


def _round_qty(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))


async def record_transaction(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    item_id: uuid.UUID,
    type_: str,
    quantity: Decimal,
    reason: str | None,
    user_id: uuid.UUID | None,
) -> InventoryItem:
    item = await InventoryItemRepository(session).get_or_404(restaurant_id, item_id)
    quantity = _round_qty(quantity)
    if quantity <= 0:
        raise BusinessRuleError(detail="Transaction quantity must be positive.")

    was_low_stock = item.is_low_stock

    if type_ == "IN":
        item.quantity = _round_qty(item.quantity + quantity)
    elif type_ == "OUT":
        if quantity > item.quantity:
            raise BusinessRuleError(detail="Not enough stock for this OUT transaction.")
        item.quantity = _round_qty(item.quantity - quantity)
    elif type_ == "ADJUSTMENT":
        item.quantity = quantity
    else:
        raise BusinessRuleError(detail=f"Unknown transaction type '{type_}'.")

    session.add(
        InventoryTransaction(
            restaurant_id=restaurant_id,
            branch_id=item.branch_id,
            inventory_item_id=item.id,
            type=type_,
            quantity=quantity,
            reason=reason,
            created_by_user_id=user_id,
        )
    )
    await session.flush()
    await session.commit()
    await session.refresh(item)

    # Alert only on the False -> True transition, not on every OUT while
    # already below minimum — one notification per dip, not one per sale.
    if not was_low_stock and item.is_low_stock:
        from app.services import notifications as notifications_service

        await notifications_service.create_notification(
            session,
            restaurant_id,
            item.branch_id,
            "LOW_STOCK",
            title=f"{item.name} kam qoldi",
            body=f"{item.quantity} {item.unit} qoldi (minimal: {item.minimum_quantity} {item.unit})",
            link="/dashboard/inventory",
        )

    return item
