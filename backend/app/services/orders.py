"""Order Engine service — the only place orders are created/transitioned.

All order sources (POS/Waiter/QR/Telegram/Delivery/Online, Section 11) funnel
into `create_order`. Order creation is ATOMIC (Section 21): order + items +
modifier snapshots + totals + table status + idempotency key in one transaction;
any failure rolls everything back. Idempotent via the `Idempotency-Key` header
(Section 11): a repeated key within the retention window returns the original
order instead of creating a second one.

Status transitions (Section 12) live ONLY in `transition_order` — applied as an
UPDATE guarded by the current DB status, so two concurrent requests cannot
double-apply a transition.
"""

import uuid
from datetime import timedelta, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.idempotency import IdempotencyKey
from app.models.menu import Product, Modifier
from app.models.order import (
    KITCHEN_STATUSES,
    ORDER_STATUSES,
    Order,
    OrderItem,
    OrderItemModifier,
)
from app.models.table import Table
from app.schemas.orders import OrderCreate
from app.services.pricing import round_money
from app.utils.errors import BusinessRuleError, ConflictError, NotFoundError

IDEMPOTENCY_WINDOW = timedelta(hours=24)

# Flat table-service charge on waiter-placed orders only (POS/QR/etc. don't
# carry a service charge). Not yet restaurant-configurable — a fixed 10% per
# current product decision; if that needs to vary per restaurant later, this
# is the one place to make it a setting.
WAITER_SERVICE_CHARGE_RATE = Decimal("0.10")

# Allowed state machine (Section 12). A completed order may later be refunded;
# a partially-paid order may later complete or refund.
_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"OPEN", "CANCELLED"},
    "OPEN": {"COMPLETED", "PARTIALLY_PAID", "CANCELLED"},
    "PARTIALLY_PAID": {"COMPLETED", "REFUNDED"},
    "COMPLETED": {"REFUNDED"},
    "CANCELLED": set(),
    "REFUNDED": set(),
}

# Single source of truth for kitchen-status transitions (Section 12). Shared by
# the orders API, the kitchen-board API and anything else that moves these states.
KITCHEN_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"NEW", "SERVED"},
    "NEW": {"PREPARING", "READY", "SERVED"},
    "PREPARING": {"READY", "SERVED"},
    "READY": {"SERVED"},
    "SERVED": set(),
}


def validate_transition(current: str, next_status: str, transitions: dict[str, set[str]]) -> None:
    if next_status not in transitions.get(current, set()):
        raise BusinessRuleError(
            detail=f"Cannot transition order from '{current}' to '{next_status}'."
        )


def _order_query():
    """Load order + items + modifiers + payments eagerly (async-safe)."""
    return (
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.modifiers),
            selectinload(Order.payments),
        )
    )


async def get_order(session: AsyncSession, restaurant_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await session.scalar(
        _order_query().where(
            Order.restaurant_id == restaurant_id, Order.id == order_id
        )
    )
    if order is None:
        raise NotFoundError(detail="Order not found in this restaurant.")
    return order


async def create_order(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    current_user_id: uuid.UUID,
    payload: OrderCreate,
    idempotency_key: str | None = None,
) -> Order:
    # --- Idempotency: same key within the window returns the original ---
    if idempotency_key:
        existing = await session.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.restaurant_id == restaurant_id,
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.expires_at > datetime.now(timezone.utc),
            )
        )
        if existing is not None:
            return await get_order(session, restaurant_id, existing.order_id)

    # Product + modifier lookups must be tenant-scoped (Section 5A).
    product_ids = {item.product_id for item in payload.items}
    products = {p.id: p for p in (await session.scalars(
        select(Product).where(
            Product.restaurant_id == restaurant_id,
            Product.id.in_(product_ids),
            Product.deleted_at.is_(None),
        )
    )).all()}
    if len(products) != len(product_ids):
        raise NotFoundError(detail="One or more products not found in this restaurant.")

    modifier_ids = {
        m.modifier_id for item in payload.items for m in item.modifiers
    }
    modifiers: dict[uuid.UUID, Modifier] = {}
    if modifier_ids:
        modifiers = {m.id: m for m in (await session.scalars(
            select(Modifier).where(
                Modifier.restaurant_id == restaurant_id,
                Modifier.id.in_(modifier_ids),
                Modifier.is_active.is_(True),
            )
        )).all()}
        if len(modifiers) != len(modifier_ids):
            raise NotFoundError(detail="One or more modifiers not found in this restaurant.")

    # Build order items with name/price snapshots (Section 13).
    order_items = []
    items_total = Decimal("0.00")
    for item in payload.items:
        product = products[item.product_id]
        if not product.is_available:
            raise BusinessRuleError(detail=f"Product '{product.name}' is not available.")
        unit_price = product.price
        line_modifiers: list[OrderItemModifier] = []
        for selection in item.modifiers:
            modifier = modifiers[selection.modifier_id]
            line_modifiers.append(
                OrderItemModifier(
                    modifier_id=modifier.id,
                    modifier_name_snapshot=modifier.name,
                    price=modifier.price,
                    quantity=selection.quantity,
                )
            )
        item_total = unit_price * item.quantity
        for lm in line_modifiers:
            item_total += lm.price * lm.quantity
        items_total += item_total
        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name_snapshot=product.name,
                unit_price=unit_price,
                quantity=item.quantity,
                discount=Decimal("0.00"),
                notes=item.notes,
                modifiers=line_modifiers,
            )
        )

    from app.services.pricing import calculate_totals

    service_charge_rate = (
        WAITER_SERVICE_CHARGE_RATE if payload.source == "WAITER" else Decimal("0.00")
    )
    totals = calculate_totals(
        items_total, payload.discount, service_charge_rate=service_charge_rate
    )

    next_number = await _next_order_number(session, restaurant_id)
    order = Order(
        restaurant_id=restaurant_id,
        branch_id=payload.branch_id,
        table_id=payload.table_id,
        order_number=next_number,
        status="DRAFT",
        source=payload.source,
        subtotal=totals.subtotal,
        discount=totals.discount,
        tax=totals.tax,
        service_charge=totals.service_charge,
        total=totals.total,
        notes=payload.notes,
        waiter_user_id=current_user_id,
        created_by_user_id=current_user_id,
        items=order_items,
    )
    session.add(order)
    await session.flush()

    if idempotency_key:
        session.add(
            IdempotencyKey(
                restaurant_id=restaurant_id,
                key=idempotency_key,
                order_id=order.id,
                expires_at=datetime.now(timezone.utc) + IDEMPOTENCY_WINDOW,
            )
        )

    # Table lifecycle (Section 10): order opened against a table claims it.
    if payload.table_id is not None:
        table = await session.scalar(
            select(Table).where(
                Table.restaurant_id == restaurant_id, Table.id == payload.table_id
            )
        )
        if table is None:
            raise NotFoundError(detail="Table not found in this restaurant.")
        if table.status == "DISABLED":
            raise BusinessRuleError(detail="Table is disabled.")
        table.status = "OCCUPIED"
        table.version += 1

    # WAITER orders go straight to the kitchen board, in the SAME transaction
    # as the order itself (Section 21/34) — previously the waiter app made a
    # second, separate PATCH call for this right after creating the order,
    # with its failure silently swallowed client-side; a blip on that second
    # call left an order the kitchen never saw, with no retry. Folding it in
    # here removes that gap: an order either reaches the kitchen atomically
    # with its own creation, or the whole creation rolls back.
    kitchen_payload = None
    if payload.source == "WAITER":
        from app.services import kitchen as kitchen_service

        order.kitchen_status = "NEW"
        ticket = await kitchen_service.create_ticket_for_order(session, restaurant_id, order)
        event = kitchen_service.event_for_status("NEW")
        if event is not None:
            kitchen_payload = kitchen_service.build_event(event, ticket)

    await session.commit()

    # Broadcast only AFTER the commit succeeds — never for a change that rolls back.
    if kitchen_payload is not None:
        from app.services import kitchen as kitchen_service

        await kitchen_service.broadcast(restaurant_id, order.branch_id, kitchen_payload)

    return await get_order(session, restaurant_id, order.id)


async def transition_order(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    new_status: str,
) -> Order:
    if new_status not in ORDER_STATUSES:
        raise BusinessRuleError(detail=f"Unknown order status '{new_status}'.")

    order = await get_order(session, restaurant_id, order_id)
    validate_transition(order.status, new_status, _TRANSITIONS)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == order.status)
        .values(
            status=new_status,
            completed_at=now if new_status in ("COMPLETED", "REFUNDED") else order.completed_at,
            cancelled_at=now if new_status == "CANCELLED" else order.cancelled_at,
        )
    )
    if result.rowcount == 0:
        raise ConflictError(detail="Order was modified concurrently. Retry.")

    # Table lifecycle (Section 10): releasing a table back to AVAILABLE happens in
    # the SAME transaction as the order terminal transition so a completed/cancelled
    # order can never leave its table stuck OCCUPIED.
    if new_status in ("COMPLETED", "CANCELLED", "REFUNDED") and order.table_id is not None:
        await session.execute(
            update(Table)
            .where(
                Table.id == order.table_id,
                Table.restaurant_id == restaurant_id,
                Table.status == "OCCUPIED",
            )
            .values(status="AVAILABLE", version=Table.version + 1)
        )

    # Kitchen board: the active ticket disappears when the order turns terminal
    # (same transaction, no orphan board tickets; Section 21).
    ticket_removed = False
    if new_status in ("COMPLETED", "CANCELLED", "REFUNDED"):
        from app.services import kitchen as kitchen_service

        ticket_removed = await kitchen_service.close_ticket_for_order(
            session, restaurant_id, order.id
        )

    await session.commit()

    # Broadcast only AFTER the commit succeeds — never for a change that rolls back.
    if ticket_removed:
        from app.services import kitchen as kitchen_service

        await kitchen_service.broadcast(
            restaurant_id,
            order.branch_id,
            {
                "event": "ticket_removed",
                "order_id": str(order.id),
                "branch_id": str(order.branch_id),
            },
        )

    return await get_order(session, restaurant_id, order_id)


async def update_kitchen_status(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    new_kitchen_status: str,
) -> Order:
    if new_kitchen_status not in KITCHEN_STATUSES:
        raise BusinessRuleError(detail=f"Unknown kitchen status '{new_kitchen_status}'.")
    order = await get_order(session, restaurant_id, order_id)
    validate_transition(order.kitchen_status, new_kitchen_status, KITCHEN_TRANSITIONS)
    # Snapshot BEFORE the UPDATE: synchronize_session expires the loaded Order,
    # so `order.kitchen_status` reads back the NEW value right after it runs.
    current_kitchen_status = order.kitchen_status
    result = await session.execute(
        update(Order)
        .where(Order.id == order.id, Order.kitchen_status == current_kitchen_status)
        .values(kitchen_status=new_kitchen_status)
    )
    if result.rowcount == 0:
        raise ConflictError(detail="Order was modified concurrently. Retry.")

    # Kitchen ticket lifecycle in the SAME transaction (Section 21): first send
    # creates the board ticket, any later status change mirrors it; the order's
    # kitchen_status stays the single source of truth (Section 34).
    from app.services import kitchen as kitchen_service

    payload = None
    event = kitchen_service.event_for_status(new_kitchen_status)
    if current_kitchen_status == "PENDING" and new_kitchen_status == "NEW":
        ticket = await kitchen_service.create_ticket_for_order(
            session, restaurant_id, order
        )
    else:
        ticket = await kitchen_service.sync_ticket_status(
            session, restaurant_id, order.id, new_kitchen_status
        )
    if ticket is not None and event is not None:
        payload = kitchen_service.build_event(event, ticket)

    await session.commit()

    # Broadcast only AFTER the commit succeeds — never for a change that rolls back.
    if payload is not None:
        await kitchen_service.broadcast(restaurant_id, order.branch_id, payload)

    return await get_order(session, restaurant_id, order_id)


async def _next_order_number(session: AsyncSession, restaurant_id: uuid.UUID) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.max(Order.order_number)).where(Order.restaurant_id == restaurant_id)
    )
    return (result.scalar() or 0) + 1