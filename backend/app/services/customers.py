"""Customer domain logic. `find_or_create` is the only place a `Customer` row
is created — called from the QR order-creation path (and, later, the
Telegram bot) so every customer is captured exactly once per identity."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.utils.errors import NotFoundError


async def find_or_create(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    *,
    phone: str | None = None,
    telegram_user_id: int | None = None,
    full_name: str | None = None,
) -> Customer:
    if telegram_user_id is not None:
        existing = await session.scalar(
            select(Customer).where(
                Customer.restaurant_id == restaurant_id,
                Customer.telegram_user_id == telegram_user_id,
            )
        )
        if existing is not None:
            return existing

    if phone:
        existing = await session.scalar(
            select(Customer).where(
                Customer.restaurant_id == restaurant_id, Customer.phone == phone
            )
        )
        if existing is not None:
            if full_name and not existing.full_name:
                existing.full_name = full_name
            return existing

    customer = Customer(
        restaurant_id=restaurant_id,
        full_name=full_name,
        phone=phone,
        telegram_user_id=telegram_user_id,
    )
    session.add(customer)
    await session.flush()
    return customer


async def list_customers(
    session: AsyncSession, restaurant_id: uuid.UUID, *, search: str | None = None, limit: int = 50, offset: int = 0
) -> list[Customer]:
    stmt = select(Customer).where(Customer.restaurant_id == restaurant_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((Customer.full_name.ilike(like)) | (Customer.phone.ilike(like)))
    stmt = stmt.order_by(Customer.created_at.desc()).limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())


async def get_customer_detail(session: AsyncSession, restaurant_id: uuid.UUID, customer_id: uuid.UUID) -> dict:
    customer = await session.scalar(
        select(Customer).where(Customer.restaurant_id == restaurant_id, Customer.id == customer_id)
    )
    if customer is None:
        raise NotFoundError(detail="Customer not found in this restaurant.")

    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(Order.total), Decimal("0.00")),
                func.count(Order.id),
                func.max(Order.created_at),
            ).where(
                Order.restaurant_id == restaurant_id,
                Order.customer_id == customer_id,
                Order.status == "COMPLETED",
            )
        )
    ).one()
    total_spent, total_orders, last_visit = totals

    favorites = (
        await session.execute(
            select(OrderItem.product_name_snapshot)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.restaurant_id == restaurant_id,
                Order.customer_id == customer_id,
                Order.status == "COMPLETED",
            )
            .group_by(OrderItem.product_name_snapshot)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(5)
        )
    ).all()

    recent = (
        await session.execute(
            select(Order)
            .where(Order.restaurant_id == restaurant_id, Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    return {
        "customer": customer,
        "total_orders": total_orders,
        "total_spent": total_spent,
        "last_visit": last_visit,
        "favorite_products": [f[0] for f in favorites],
        "recent_orders": list(recent),
    }
