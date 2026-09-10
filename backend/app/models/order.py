"""Order Engine domain: Order, OrderItem, OrderItemModifier.

The single central Order Engine (Section 11) — every source (POS, Waiter, QR,
Telegram, Online, Delivery) funnels through `Order`; downstream consumers
(Kitchen, Cashier, Inventory, CRM, Analytics, AI) all reference the same
central tables. Nothing recreates order data independently (Section 34).

Money: `subtotal/discount/tax/total` are Numeric(12,2)/Decimal, rounding handled
once in `app/services/pricing.py` (Section 12A). Order items snapshot
`product_name_snapshot` + `unit_price` so historical orders stay correct if the
product changes later (Section 13).

Order status transitions live in ONE state-machine function
(`app/services/orders.py`), never scattered `if`s (Section 12).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, uuid_pk

# Order lifecycle (Section 12). DRAFT = mid-build, OPEN = sent to kitchen /
# in service, COMPLETED = paid & delivered, PARTIALLY_PAID = split/staged
# payment, CANCELLED / REFUNDED = terminal.
ORDER_STATUSES = (
    "DRAFT",
    "OPEN",
    "COMPLETED",
    "CANCELLED",
    "PARTIALLY_PAID",
    "REFUNDED",
)

ORDER_SOURCES = ("POS", "WAITER", "QR", "TELEGRAM", "DELIVERY", "ONLINE")

# Per-ticket kitchen status flows NEW -> PREPARING -> READY -> SERVED (Section 16).
KITCHEN_STATUSES = ("PENDING", "NEW", "PREPARING", "READY", "SERVED")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    # One uninterrupted order-number sequence per restaurant.
    __table_args__ = (
        UniqueConstraint("restaurant_id", "order_number", name="uq_orders_restaurant_order_number"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Tenant scope: NOT NULL + index (Section 5A).
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: delivery / QR-to-go orders may have no assigned table.
    table_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tables.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    kitchen_status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(20), default="POS", nullable=False, index=True
    )

    # Money: Numeric(12,2) / Decimal, never float (Section 12A). Computed in the
    # restaurant's currency by `app/services/pricing.py`.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)
    # Who is serving / created this (audit, Section 6.3).
    waiter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Prevents double-close / double-cancel racing (locks are also enforced in
    # the state-machine function with a transaction).
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items = relationship(
        "OrderItem",
        back_populates="order",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    payments = relationship("Payment", back_populates="order", lazy="selectin")
    # Resolved for kitchen tickets / displays; NULL when delivery/QR-to-go.
    table = relationship(
        "Table",
        lazy="selectin",
        foreign_keys=[table_id],
        viewonly=True,
    )


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot (Section 13): name + price copied at order-item creation time so
    # later product edits never mutate historical orders.
    product_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    order = relationship("Order", back_populates="items")
    modifiers = relationship(
        "OrderItemModifier",
        back_populates="item",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class OrderItemModifier(Base, TimestampMixin):
    __tablename__ = "order_item_modifiers"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modifier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("modifiers.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot of the modifier (name + price) at selection time.
    modifier_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    item = relationship("OrderItem", back_populates="modifiers")