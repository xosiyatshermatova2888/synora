"""Payment + cash shift domain logic.

Supports multiple payments per order (Section 14): each call adds a row to
`payments`. When cumulative paid amount reaches the order total the order
transitions OPEN/PARTIALLY_PAID -> COMPLETED via the order state machine; a
partial payment leaves it PARTIALLY_PAID. Cash shifts use optimistic locking on
close (Section 15).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.payment import CashShift, Payment
from app.services import orders as order_service
from app.services.pricing import round_money
from app.utils.errors import BusinessRuleError, ConflictError, NotFoundError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def add_payment(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    current_user_id: uuid.UUID,
    order_id: uuid.UUID,
    amount: Decimal,
    method: str,
    reference: str | None,
) -> Payment:
    order = await order_service.get_order(session, restaurant_id, order_id)
    if order.status not in ("OPEN", "PARTIALLY_PAID"):
        # DRAFT is intentionally NOT payable: the order state machine has no
        # DRAFT -> COMPLETED / DRAFT -> PARTIALLY_PAID transition (Section 12),
        # so accepting payment here would always 422 downstream. Open the order
        # first (PATCH /orders/{id}/status OPEN).
        raise BusinessRuleError(detail="Order is not open for payment.")

    amount = round_money(amount)
    if amount <= 0:
        raise BusinessRuleError(detail="Payment amount must be positive.")

    paid = await total_paid(session, restaurant_id, order_id)
    remaining = order.total - paid
    if amount > remaining:
        raise BusinessRuleError(detail="Payment exceeds the outstanding balance.")

    payment = Payment(
        restaurant_id=restaurant_id,
        order_id=order.id,
        amount=amount,
        method=method,
        status="PAID",
        reference=reference,
        created_by_user_id=current_user_id,
    )
    session.add(payment)
    await session.flush()

    new_paid = paid + amount
    if new_paid >= order.total:
        # Fully paid: complete the order regardless of the number of payments.
        await order_service.transition_order(session, restaurant_id, order.id, "COMPLETED")
    elif order.status != "PARTIALLY_PAID":
        await order_service.transition_order(session, restaurant_id, order.id, "PARTIALLY_PAID")

    await session.commit()
    return payment


async def open_shift(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID,
    cashier_user_id: uuid.UUID,
    opening_balance: Decimal,
) -> CashShift:
    existing = await session.scalar(
        select(CashShift).where(
            CashShift.restaurant_id == restaurant_id,
            CashShift.branch_id == branch_id,
            CashShift.status == "OPEN",
            CashShift.is_active.is_(True),
        )
    )
    if existing is not None:
        raise BusinessRuleError(detail="A cash shift is already open for this branch.")

    shift = CashShift(
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        cashier_user_id=cashier_user_id,
        opened_at=_utcnow(),
        opening_balance=round_money(opening_balance),
        status="OPEN",
    )
    session.add(shift)
    await session.flush()
    await session.commit()
    return shift


async def close_shift(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    shift_id: uuid.UUID,
    actual_closing_balance: Decimal,
    expected_version: int,
) -> CashShift:
    shift = await session.scalar(
        select(CashShift).where(
            CashShift.restaurant_id == restaurant_id, CashShift.id == shift_id
        )
    )
    if shift is None:
        raise NotFoundError(detail="Cash shift not found in this restaurant.")
    if shift.status != "OPEN":
        raise BusinessRuleError(detail="Cash shift is already closed.")
    if shift.version != expected_version:
        raise ConflictError(detail="Cash shift was modified concurrently. Retry.")

    # Expected = opening balance + cash payments collected during the shift.
    cash_paid = await _cash_paid_since(session, restaurant_id, shift.branch_id, shift.opened_at)
    expected = round_money(shift.opening_balance + cash_paid)

    shift.expected_closing_balance = expected
    shift.actual_closing_balance = round_money(actual_closing_balance)
    shift.closed_at = _utcnow()
    shift.status = "CLOSED"
    shift.version += 1
    await session.flush()
    await session.commit()
    return shift


async def total_paid(session: AsyncSession, restaurant_id: uuid.UUID, order_id: uuid.UUID) -> Decimal:
    from sqlalchemy import func

    result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0.00"))).where(
            Payment.restaurant_id == restaurant_id,
            Payment.order_id == order_id,
            Payment.status == "PAID",
        )
    )
    return result.scalar() or Decimal("0.00")


async def _cash_paid_since(
    session: AsyncSession, restaurant_id: uuid.UUID, branch_id: uuid.UUID, since: datetime
) -> Decimal:
    from sqlalchemy import func

    from app.models.order import Order

    result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0.00"))).where(
            Payment.restaurant_id == restaurant_id,
            Payment.method == "CASH",
            Payment.status == "PAID",
            Payment.created_at >= since,
            Payment.order_id.in_(
                select(Order.id).where(
                    Order.restaurant_id == restaurant_id,
                    Order.branch_id == branch_id,
                )
            ),
        )
    )
    return result.scalar() or Decimal("0.00")
