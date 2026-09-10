"""Kitchen module service (Phase K).

The ticket is a VIEW over the order (Section 34): ticket creation, status sync
and removal all happen inside the SAME database transaction as the order update
that drives them (Section 21 — no partial state). Real status transitions never
happen here — they funnel through the single order state machine
(`app/services/orders.py::update_kitchen_status`), the one authority on
`Order.kitchen_status`.

After the caller commits, `broadcast()` fans the corresponding event out over
the per-tenant WebSocket registry (`app/websocket/manager.py`). Broadcasts only
ever run AFTER a successful commit, so an event is never emitted for a change
that might roll back.
"""

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kitchen import (
    KITCHEN_TICKET_ACTIVE,
    KitchenTicket,
)
from app.repositories.kitchen import KitchenTicketRepository
from app.utils.errors import BusinessRuleError
from app.websocket.manager import manager

# Board statuses the ticket endpoint may propose. The actual transition validity
# is enforced by the order engine's machine; this is only an allowed-proposal set.
TICKET_BOARD_STATUSES = ("NEW", "PREPARING", "READY")

_EVENT_BY_STATUS = {
    "NEW": "order_sent_to_kitchen",
    "PREPARING": "order_preparing",
    "READY": "order_ready",
    "SERVED": "order_served",
}


def event_for_status(status: str) -> str | None:
    """Map an order kitchen status to its WebSocket event name.

    SERVED is included so ~existing orders-page flows~ that skip a ticket keep
    the board live-consistent (the ticket row falls off the board's active set).
    """
    return _EVENT_BY_STATUS.get(status)


def serialize(ticket: KitchenTicket) -> dict:
    """Enrich a ticket into the board payload using the central order."""
    order = ticket.order
    return {
        "id": str(ticket.id),
        "restaurant_id": str(ticket.restaurant_id),
        "branch_id": str(ticket.branch_id),
        "order_id": str(ticket.order_id),
        "order_number": order.order_number,
        "table_name": order.table.name if order.table is not None else None,
        "station_id": str(ticket.station_id) if ticket.station_id else None,
        "status": ticket.status,
        "notes": order.notes,
        "source": order.source,
        "items": [
            {
                "product_name_snapshot": item.product_name_snapshot,
                "quantity": item.quantity,
                "notes": item.notes,
                "modifiers": [
                    {
                        "modifier_name_snapshot": m.modifier_name_snapshot,
                        "quantity": m.quantity,
                    }
                    for m in item.modifiers
                ],
            }
            for item in order.items
        ],
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
    }


def build_event(event: str, ticket: KitchenTicket) -> dict:
    """Wire payload for a ticket event: {event, ticket}."""
    return {"event": event, "ticket": serialize(ticket)}


async def broadcast(restaurant_id: uuid.UUID, branch_id: uuid.UUID, payload: dict) -> None:
    """Push an already-committed event to every connection in the tenant."""
    await manager.broadcast(restaurant_id, branch_id, payload)


# ---------------------------------------------------------------------------
# Ticket lifecycle — called by the order engine inside its own transaction
# (these functions never commit and never broadcast).
# ---------------------------------------------------------------------------
async def create_ticket_for_order(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order,
) -> KitchenTicket:
    """Create the board ticket on the first kitchen send (PENDING -> NEW)."""
    repo = KitchenTicketRepository(session)
    existing = await repo.find_active_for_order(restaurant_id, order.id)
    if existing is not None:
        return existing
    ticket = KitchenTicket(
        restaurant_id=restaurant_id,
        branch_id=order.branch_id,
        order_id=order.id,
        status="NEW",
    )
    session.add(ticket)
    await session.flush()
    return ticket


async def sync_ticket_status(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    new_status: str,
) -> KitchenTicket | None:
    """Mirror the order's kitchen status onto the active ticket (if any)."""
    repo = KitchenTicketRepository(session)
    ticket = await repo.find_active_for_order(restaurant_id, order_id)
    if ticket is None:
        return None
    ticket.status = new_status
    await session.flush()
    return ticket


async def close_ticket_for_order(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
) -> bool:
    """Remove the active ticket when the order turns terminal. Returns True if a
    ticket row was actually deleted (so the caller can broadcast the removal)."""
    result = await session.execute(
        delete(KitchenTicket).where(
            KitchenTicket.restaurant_id == restaurant_id,
            KitchenTicket.order_id == order_id,
            KitchenTicket.status.in_(KITCHEN_TICKET_ACTIVE),
        )
    )
    await session.flush()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Ticket endpoint entry point (Phase K API)
# ---------------------------------------------------------------------------
async def advance_ticket_status(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    ticket_id: uuid.UUID,
    new_status: str,
) -> dict:
    """Advance a board ticket. Real transition authority is the order engine.

    The endpoint may only propose board statuses; `update_kitchen_status` then
    validates against the order machine, applies order + ticket mirror in ONE
    transaction, commits and broadcasts. Returns the refreshed serialized ticket.
    """
    if new_status not in TICKET_BOARD_STATUSES:
        raise BusinessRuleError(
            detail=f"Ticket status '{new_status}' is not a kitchen-board status."
        )
    repo = KitchenTicketRepository(session)
    ticket = await repo.get_or_404(restaurant_id, ticket_id)
    if ticket.status == new_status:
        raise BusinessRuleError(detail="Ticket is already in that status.")

    from app.services import orders as order_service

    await order_service.update_kitchen_status(
        session, restaurant_id, ticket.order_id, new_status
    )
    await session.refresh(ticket)
    return serialize(ticket)