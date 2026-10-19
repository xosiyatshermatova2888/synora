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

from app.services.subscription import ensure_can_write
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
from app.utils.tenant_refs import require_branch

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


async def announce_order_change(restaurant_id: uuid.UUID, branch_id: uuid.UUID, order_id: uuid.UUID) -> None:
    """Tell every open dashboard of this restaurant that orders changed, so lists
    refresh by themselves (no manual reload). Fail-soft: never blocks the order."""
    try:
        from app.websocket.manager import manager

        await manager.broadcast(
            restaurant_id,
            branch_id,
            {"event": "order_changed", "order_id": str(order_id), "branch_id": str(branch_id)},
        )
    except Exception:  # noqa: BLE001
        pass


async def create_order(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    current_user_id: uuid.UUID | None,
    payload: OrderCreate,
    idempotency_key: str | None = None,
    customer_id: uuid.UUID | None = None,
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

    await require_branch(session, restaurant_id, payload.branch_id)

    # A lapsed subscription (past grace) stops every channel — staff, QR and
    # Telegram alike — from creating orders.
    await ensure_can_write(session, restaurant_id)

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

    from app.services.pricing import calculate_totals, resolve_discount

    service_charge_rate = (
        WAITER_SERVICE_CHARGE_RATE if payload.source == "WAITER" else Decimal("0.00")
    )
    discount_amount = resolve_discount(items_total, payload.discount_type, payload.discount)
    totals = calculate_totals(
        items_total, discount_amount, service_charge_rate=service_charge_rate
    )

    next_number = await _next_order_number(session, restaurant_id)
    order = Order(
        restaurant_id=restaurant_id,
        branch_id=payload.branch_id,
        table_id=payload.table_id,
        order_number=next_number,
        # WAITER/QR/TELEGRAM orders go straight to the kitchen, so they are
        # confirmed (OPEN) from the start; a DRAFT order cannot take payment,
        # which would leave the cashier unable to settle them.
        status="OPEN" if payload.source in ("WAITER", "QR", "TELEGRAM") else "DRAFT",
        source=payload.source,
        subtotal=totals.subtotal,
        discount_type=payload.discount_type,
        discount=totals.discount,
        tax=totals.tax,
        service_charge=totals.service_charge,
        total=totals.total,
        notes=payload.notes,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        delivery_type=payload.delivery_type,
        delivery_address=payload.delivery_address,
        delivery_lat=payload.delivery_lat,
        delivery_lng=payload.delivery_lng,
        delivery_note=payload.delivery_note,
        payment_method=payload.payment_method,
        waiter_user_id=current_user_id,
        created_by_user_id=current_user_id,
        customer_id=customer_id,
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
        if table is None or table.branch_id != payload.branch_id:
            raise NotFoundError(detail="Table not found in this restaurant.")
        if table.status == "DISABLED":
            raise BusinessRuleError(detail="Table is disabled.")
        table.status = "OCCUPIED"
        table.version += 1

    # WAITER/QR/TELEGRAM orders go straight to the kitchen board, in the SAME
    # transaction as the order itself (Section 21/34) — previously the waiter
    # app made a second, separate PATCH call for this right after creating
    # the order, with its failure silently swallowed client-side; a blip on
    # that second call left an order the kitchen never saw, with no retry.
    # Folding it in here removes that gap: an order either reaches the
    # kitchen atomically with its own creation, or the whole creation rolls
    # back. QR/TELEGRAM orders get the same treatment as WAITER: nobody on
    # staff is mediating the order, so the kitchen needs to see it immediately.
    kitchen_payload = None
    if payload.source in ("WAITER", "QR", "TELEGRAM"):
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

        from app.services import printing as printing_service

        await printing_service.schedule_kitchen_ticket(restaurant_id, order.branch_id, order.id)
        await printing_service.schedule_order_copy(restaurant_id, order.branch_id, order.id)

    # A customer-placed order (nobody on staff pressed a button for it) is
    # worth an alert; POS/WAITER orders are already staff-visible by nature.
    if payload.source in ("QR", "TELEGRAM"):
        from app.services import notifications as notifications_service

        await notifications_service.create_notification(
            session,
            restaurant_id,
            order.branch_id,
            "NEW_ORDER",
            title=f"Yangi buyurtma #{order.order_number}",
            body=f"{payload.source} orqali {order.total} {order.currency}",
            link="/dashboard/orders",
        )

    await announce_order_change(restaurant_id, order.branch_id, order.id)
    return await get_order(session, restaurant_id, order.id)


async def transition_order(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    new_status: str,
    current_user_id: uuid.UUID | None = None,
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
    await announce_order_change(restaurant_id, order.branch_id, order.id)

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

    if new_status in ("CANCELLED", "REFUNDED"):
        from app.services import audit as audit_service

        await audit_service.log_action(
            session,
            restaurant_id,
            current_user_id,
            f"order.{new_status.lower()}",
            "order",
            order.id,
            f"Order #{order.order_number} {new_status.lower()}",
        )

    if new_status == "CANCELLED":
        from app.services import notifications as notifications_service

        await notifications_service.create_notification(
            session,
            restaurant_id,
            order.branch_id,
            "ORDER_CANCELLED",
            title=f"Buyurtma #{order.order_number} bekor qilindi",
            link="/dashboard/orders",
        )

        from app.services import customer_notify

        await customer_notify.notify(restaurant_id, order.id, "CANCELLED")

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
    await announce_order_change(restaurant_id, order.branch_id, order.id)
    if current_kitchen_status == "PENDING" and new_kitchen_status == "NEW":
        from app.services import printing as printing_service

        await printing_service.schedule_kitchen_ticket(restaurant_id, order.branch_id, order.id)
        await printing_service.schedule_order_copy(restaurant_id, order.branch_id, order.id)
    if new_kitchen_status in ("PREPARING", "READY", "SERVED"):
        from app.services import customer_notify

        await customer_notify.notify(restaurant_id, order.id, new_kitchen_status)

    return await get_order(session, restaurant_id, order_id)


async def _next_order_number(session: AsyncSession, restaurant_id: uuid.UUID) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.max(Order.order_number)).where(Order.restaurant_id == restaurant_id)
    )
    return (result.scalar() or 0) + 1


def _items_total(order: Order) -> Decimal:
    total = Decimal("0.00")
    for item in order.items:
        line = item.unit_price * item.quantity
        for modifier in item.modifiers:
            line += modifier.price * modifier.quantity
        total += line - item.discount
    return total


async def apply_discount(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    discount_type: str,
    discount_value: Decimal,
    current_user_id: uuid.UUID | None = None,
) -> Order:
    """Re-price an already-open order with a new discount (Section 8).

    Only while DRAFT/OPEN — an order with payments recorded against it keeps
    the discount it was paid under; re-pricing it would desync `total` from
    what was actually collected.
    """
    from app.services.pricing import calculate_totals, resolve_discount

    order = await get_order(session, restaurant_id, order_id)
    if order.status not in ("DRAFT", "OPEN"):
        raise BusinessRuleError(detail="Discount can only be applied to a DRAFT or OPEN order.")

    items_total = _items_total(order)
    service_charge_rate = (
        WAITER_SERVICE_CHARGE_RATE if order.source == "WAITER" else Decimal("0.00")
    )
    discount_amount = resolve_discount(items_total, discount_type, discount_value)
    totals = calculate_totals(items_total, discount_amount, service_charge_rate=service_charge_rate)

    order.discount_type = discount_type
    order.subtotal = totals.subtotal
    order.discount = totals.discount
    order.tax = totals.tax
    order.service_charge = totals.service_charge
    order.total = totals.total
    await session.flush()
    await session.commit()

    from app.services import audit as audit_service

    label = f"{discount_value}%" if discount_type == "PERCENT" else f"{discount_value}"
    await audit_service.log_action(
        session,
        restaurant_id,
        current_user_id,
        "order.discount",
        "order",
        order.id,
        f"Applied {label} discount to order #{order.order_number}",
    )

    return await get_order(session, restaurant_id, order_id)


async def transfer_table(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    order_id: uuid.UUID,
    new_table_id: uuid.UUID,
) -> Order:
    """Move an order to a different table (Section 3). Same optimistic-lock
    convention as `transition_order`'s table release (`Table.version`)."""
    order = await get_order(session, restaurant_id, order_id)
    if order.status in ("COMPLETED", "CANCELLED", "REFUNDED"):
        raise BusinessRuleError(detail="Cannot transfer a closed order to another table.")

    new_table = await session.scalar(
        select(Table).where(Table.restaurant_id == restaurant_id, Table.id == new_table_id)
    )
    if new_table is None:
        raise NotFoundError(detail="Table not found in this restaurant.")
    if new_table.status == "DISABLED":
        raise BusinessRuleError(detail="Table is disabled.")
    if new_table.status == "OCCUPIED" and new_table.id != order.table_id:
        raise BusinessRuleError(detail="Table is already occupied by another order.")

    old_table_id = order.table_id
    if old_table_id is not None and old_table_id != new_table_id:
        other_open = await session.scalar(
            select(Order.id).where(
                Order.restaurant_id == restaurant_id,
                Order.table_id == old_table_id,
                Order.id != order.id,
                Order.status.in_(("DRAFT", "OPEN", "PARTIALLY_PAID")),
            )
        )
        if other_open is None:
            await session.execute(
                update(Table)
                .where(Table.id == old_table_id, Table.restaurant_id == restaurant_id)
                .values(status="AVAILABLE", version=Table.version + 1)
            )

    order.table_id = new_table_id
    if new_table.status != "OCCUPIED":
        new_table.status = "OCCUPIED"
        new_table.version += 1

    await session.flush()
    await session.commit()
    return await get_order(session, restaurant_id, order_id)


async def merge_orders(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    source_order_id: uuid.UUID,
    target_order_id: uuid.UUID,
) -> Order:
    """Fold one table's order into another's (Section 3): move the items,
    re-price the target, cancel the (now empty) source through the normal
    state machine — which already frees its table and removes its kitchen
    ticket (Section 21), so no extra logic is needed here for that part.

    Restricted to DRAFT/OPEN orders on both sides: PARTIALLY_PAID has no
    DRAFT/OPEN-style CANCELLED transition (money is already collected against
    it), so merging one would need a refund flow, not a merge.
    """
    if source_order_id == target_order_id:
        raise BusinessRuleError(detail="Cannot merge an order into itself.")

    source = await get_order(session, restaurant_id, source_order_id)
    target = await get_order(session, restaurant_id, target_order_id)

    if source.branch_id != target.branch_id:
        raise BusinessRuleError(detail="Orders must be in the same branch to merge.")
    for order in (source, target):
        if order.status not in ("DRAFT", "OPEN"):
            raise BusinessRuleError(
                detail=f"Order #{order.order_number} must be DRAFT or OPEN to merge."
            )

    from app.services.pricing import calculate_totals

    await session.execute(
        update(OrderItem).where(OrderItem.order_id == source.id).values(order_id=target.id)
    )
    await session.flush()
    await session.refresh(target)  # re-load so target.items reflects the moved rows

    items_total = _items_total(target)
    service_charge_rate = (
        WAITER_SERVICE_CHARGE_RATE if target.source == "WAITER" else Decimal("0.00")
    )
    # Keep the target's existing discount amount as-is (not auto-rescaled) —
    # simplest, predictable behavior; the cashier re-applies a discount via
    # `apply_discount` afterward if the merged bill should be discounted too.
    totals = calculate_totals(items_total, target.discount, service_charge_rate=service_charge_rate)
    target.subtotal = totals.subtotal
    target.tax = totals.tax
    target.service_charge = totals.service_charge
    target.total = totals.total
    await session.flush()
    await session.commit()

    await transition_order(session, restaurant_id, source.id, "CANCELLED")

    return await get_order(session, restaurant_id, target.id)


async def waiter_stats(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    waiter_user_id: uuid.UUID,
    date_from: datetime,
    date_to: datetime,
) -> dict:
    """Aggregate in SQL, not in Python (Section 15's waiter-stats ask) — avoids
    the same "pull N rows and reduce client-side" trap the main dashboard has."""
    from sqlalchemy import func

    completed = (
        await session.execute(
            select(
                func.coalesce(func.sum(Order.total), Decimal("0.00")),
                func.count(Order.id),
                func.count(func.distinct(Order.table_id)),
            ).where(
                Order.restaurant_id == restaurant_id,
                Order.waiter_user_id == waiter_user_id,
                Order.status == "COMPLETED",
                Order.created_at >= date_from,
                Order.created_at < date_to,
            )
        )
    ).one()
    total_sales, order_count, tables_served = completed

    cancelled_count = await session.scalar(
        select(func.count(Order.id)).where(
            Order.restaurant_id == restaurant_id,
            Order.waiter_user_id == waiter_user_id,
            Order.status == "CANCELLED",
            Order.created_at >= date_from,
            Order.created_at < date_to,
        )
    ) or 0

    average_check = round_money(total_sales / order_count) if order_count else Decimal("0.00")
    return {
        "waiter_user_id": waiter_user_id,
        "date_from": date_from,
        "date_to": date_to,
        "total_sales": total_sales,
        "order_count": order_count,
        "tables_served": tables_served,
        "average_check": average_check,
        "cancelled_count": cancelled_count,
    }


async def request_bill(session: AsyncSession, restaurant_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    """A waiter asks the cashier to bring the bill for this order. Idempotent:
    the first request stamps `bill_requested_at` and notifies the cashier; later
    taps are no-ops."""
    order = await get_order(session, restaurant_id, order_id)
    if order.status not in ("OPEN", "PARTIALLY_PAID"):
        raise BusinessRuleError(detail="Only an open order can request its bill.")
    if order.bill_requested_at is not None:
        return order

    order.bill_requested_at = datetime.now(timezone.utc)
    await session.commit()
    await announce_order_change(restaurant_id, order.branch_id, order.id)

    from app.services import notifications as notifications_service

    where = f"Stol {order.table.name}" if order.table is not None else f"#{order.order_number}"
    await notifications_service.create_notification(
        session,
        restaurant_id,
        order.branch_id,
        "BILL_REQUEST",
        title=f"{where}: hisob so'raldi",
        body=f"Buyurtma #{order.order_number} — {order.total} {order.currency}",
        link="/dashboard/payments",
    )
    return await get_order(session, restaurant_id, order_id)


async def attach_payment_proof(
    session: AsyncSession, restaurant_id: uuid.UUID, order_id: uuid.UUID, url: str
) -> Order:
    """Store the customer's card-transfer receipt image on the order."""
    order = await get_order(session, restaurant_id, order_id)
    order.payment_proof_url = url
    await session.commit()
    return await get_order(session, restaurant_id, order_id)
