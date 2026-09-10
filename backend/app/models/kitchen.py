"""Kitchen module: kitchen stations + kitchen tickets (Phase K).

A kitchen ticket is a VIEW/workflow object over the already-existing Order
(Section 34, "one central Order Engine"): it references `order_id` and carries
NO order/line-item data of its own. The order stays the single source of truth —
`KitchenTicket.status` always mirrors `Order.kitchen_status`, and the ticket row
exists only so the kitchen board can list "what's cooking" per branch without
pulling full orders.

Ticket lifecycle (Section 16): created the first time an order is sent to the
kitchen (`order.kitchen_status` PENDING -> NEW), then moves NEW -> PREPARING ->
READY -> SERVED. The board shows only NEW/PREPARING/READY; SERVED tickets fall
off the board, and terminal order statuses (COMPLETED/CANCELLED/REFUNDED)
delete the active ticket row entirely.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, uuid_pk

# Statuses a ticket can ever hold — mirrors order.kitchen_status values.
KITCHEN_TICKET_STATUSES = ("NEW", "PREPARING", "READY", "SERVED")

# Statuses that are still "on the kitchen board".
KITCHEN_TICKET_ACTIVE = ("NEW", "PREPARING", "READY")


class KitchenStation(Base, TimestampMixin):
    __tablename__ = "kitchen_stations"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Tenant scope: NOT NULL + index (Section 5A).
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class KitchenTicket(Base, TimestampMixin):
    __tablename__ = "kitchen_tickets"
    # One workflow ticket per order within a restaurant. Terminal order statuses
    # delete the row, so a re-opened order would start a fresh ticket.
    __table_args__ = (
        UniqueConstraint(
            "restaurant_id", "order_id",
            name="uq_kitchen_tickets_restaurant_order",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Tenant scope: NOT NULL + index (Section 5A).
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kitchen_stations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Mirror of `order.kitchen_status` (single source of truth stays the order).
    status: Mapped[str] = mapped_column(
        String(20), default="NEW", nullable=False, index=True
    )

    order = relationship("Order", lazy="selectin")