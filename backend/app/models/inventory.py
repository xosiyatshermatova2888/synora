"""Inventory domain: InventoryItem, InventoryTransaction.

Tracks raw/stock items (e.g. "Pomidor", "Go'sht") as their own ledger,
separate from sellable menu `Product`s (`app/models/menu.py`) — there is no
recipe/BOM link between the two yet, so selling a menu item does not
auto-deduct stock. Staff log kirim/chiqim/adjustment transactions by hand via
`app/services/inventory.py::record_transaction`, which is the only place
`InventoryItem.quantity` is ever written, keeping the running balance and its
transaction history always consistent with each other.

Money on `cost_per_unit` is `Numeric(12,2)` like everywhere else; `quantity`/
`minimum_quantity` use `Numeric(12,3)` since stock (kg, l) needs sub-unit
precision that currency doesn't.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk

INVENTORY_TRANSACTION_TYPES = ("IN", "OUT", "ADJUSTMENT")


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Stock is tracked per branch, not pooled restaurant-wide.
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # "kg", "l", "dona"
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.000"), nullable=False)
    minimum_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.000"), nullable=False)
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    supplier: Mapped[str | None] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.minimum_quantity


class InventoryTransaction(Base, TimestampMixin):
    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Always positive. For IN/OUT this is the delta applied; for ADJUSTMENT
    # this is the resulting absolute quantity (see record_transaction).
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
