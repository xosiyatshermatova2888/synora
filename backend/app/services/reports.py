"""Reports/Analytics — real aggregation over Order/OrderItem/Payment/Expense,
generalizing the SQL-aggregation pattern already used by
`app/services/orders.py::waiter_stats` instead of pulling rows into Python
and reducing them client-side (the Overview page's pre-Phase-2 approach).

`sales_series`'s day/week/month bucketing is the one exception: Postgres has
`date_trunc`, but this project's test suite runs on SQLite
(`sqlite+aiosqlite`, see `tests/conftest.py`) which doesn't, so bucketing
happens in Python over a bounded (date-range-limited) row set instead of a
dialect-specific SQL function — the other reports below have no such
portability constraint and aggregate entirely in SQL.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.services.pricing import round_money


def _scope(stmt, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None, model=Order):
    stmt = stmt.where(model.restaurant_id == restaurant_id)
    if branch_id is not None:
        stmt = stmt.where(model.branch_id == branch_id)
    return stmt


async def sales_series(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    date_from: date,
    date_to: date,
    group_by: str,
) -> list[dict]:
    stmt = _scope(select(Order.created_at, Order.total), restaurant_id, branch_id).where(
        Order.status == "COMPLETED",
        func.date(Order.created_at) >= date_from,
        func.date(Order.created_at) <= date_to,
    )
    rows = (await session.execute(stmt)).all()

    def bucket_key(d: date) -> date:
        if group_by == "week":
            return d - timedelta(days=d.weekday())
        if group_by == "month":
            return d.replace(day=1)
        return d

    buckets: dict[date, dict] = {}
    for created_at, total in rows:
        key = bucket_key(created_at.date())
        entry = buckets.setdefault(key, {"revenue": Decimal("0.00"), "order_count": 0})
        entry["revenue"] += total
        entry["order_count"] += 1

    return [
        {"bucket": key, "revenue": round_money(v["revenue"]), "order_count": v["order_count"]}
        for key, v in sorted(buckets.items())
    ]


async def product_report(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    date_from: date,
    date_to: date,
) -> list[dict]:
    stmt = (
        select(
            OrderItem.product_name_snapshot,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.unit_price * OrderItem.quantity),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.restaurant_id == restaurant_id,
            Order.status == "COMPLETED",
            func.date(Order.created_at) >= date_from,
            func.date(Order.created_at) <= date_to,
        )
        .group_by(OrderItem.product_name_snapshot)
        .order_by(func.sum(OrderItem.unit_price * OrderItem.quantity).desc())
    )
    if branch_id is not None:
        stmt = stmt.where(Order.branch_id == branch_id)
    rows = (await session.execute(stmt)).all()
    return [
        {"product_name": name, "quantity": int(qty), "revenue": round_money(revenue)}
        for name, qty, revenue in rows
    ]


async def waiter_report(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    date_from: date,
    date_to: date,
) -> list[dict]:
    stmt = (
        select(
            Order.waiter_user_id,
            User.full_name,
            func.coalesce(func.sum(Order.total), Decimal("0.00")),
            func.count(Order.id),
        )
        .join(User, User.id == Order.waiter_user_id)
        .where(
            Order.restaurant_id == restaurant_id,
            Order.waiter_user_id.is_not(None),
            Order.status == "COMPLETED",
            func.date(Order.created_at) >= date_from,
            func.date(Order.created_at) <= date_to,
        )
        .group_by(Order.waiter_user_id, User.full_name)
        .order_by(func.sum(Order.total).desc())
    )
    if branch_id is not None:
        stmt = stmt.where(Order.branch_id == branch_id)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "waiter_user_id": waiter_id,
            "waiter_name": name,
            "total_sales": round_money(total),
            "order_count": count,
            "average_check": round_money(total / count) if count else Decimal("0.00"),
        }
        for waiter_id, name, total, count in rows
    ]


async def payment_report(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    date_from: date,
    date_to: date,
) -> list[dict]:
    stmt = (
        select(Payment.method, func.sum(Payment.amount), func.count(Payment.id))
        .join(Order, Order.id == Payment.order_id)
        .where(
            Payment.restaurant_id == restaurant_id,
            Payment.status == "PAID",
            func.date(Payment.created_at) >= date_from,
            func.date(Payment.created_at) <= date_to,
        )
        .group_by(Payment.method)
        .order_by(func.sum(Payment.amount).desc())
    )
    if branch_id is not None:
        stmt = stmt.where(Order.branch_id == branch_id)
    rows = (await session.execute(stmt)).all()
    return [{"method": method, "amount": round_money(amount), "count": count} for method, amount, count in rows]


async def expense_report(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    date_from: date,
    date_to: date,
) -> list[dict]:
    stmt = (
        select(Expense.category, func.sum(Expense.amount))
        .where(
            Expense.restaurant_id == restaurant_id,
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
        )
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    )
    if branch_id is not None:
        stmt = stmt.where(Expense.branch_id == branch_id)
    rows = (await session.execute(stmt)).all()
    return [{"category": category, "amount": round_money(amount)} for category, amount in rows]


async def profit_report(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    date_from: date,
    date_to: date,
) -> dict:
    revenue_stmt = _scope(
        select(func.coalesce(func.sum(Order.total), Decimal("0.00"))), restaurant_id, branch_id
    ).where(
        Order.status == "COMPLETED",
        func.date(Order.created_at) >= date_from,
        func.date(Order.created_at) <= date_to,
    )
    revenue = await session.scalar(revenue_stmt) or Decimal("0.00")

    expense_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
        Expense.restaurant_id == restaurant_id,
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    )
    if branch_id is not None:
        expense_stmt = expense_stmt.where(Expense.branch_id == branch_id)
    expenses = await session.scalar(expense_stmt) or Decimal("0.00")

    return {
        "revenue": round_money(revenue),
        "expenses": round_money(expenses),
        "profit": round_money(revenue - expenses),
    }
