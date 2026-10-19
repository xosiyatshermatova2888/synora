"""Global search — generalizes `services/customers.py::list_customers`'s
`ilike` pattern across the entities the spec asks for (Order ID, Product,
Customer, Waiter, Table), each tenant-scoped first, capped per type.
"""

import uuid

from sqlalchemy import cast, or_, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.menu import Product
from app.models.order import Order
from app.models.table import Table
from app.models.user import User


async def global_search(
    session: AsyncSession, restaurant_id: uuid.UUID, query: str, limit_per_type: int = 5
) -> dict:
    like = f"%{query}%"

    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.restaurant_id == restaurant_id, cast(Order.order_number, String).ilike(like))
                .order_by(Order.created_at.desc())
                .limit(limit_per_type)
            )
        ).all()
    )
    products = list(
        (
            await session.scalars(
                select(Product)
                .where(
                    Product.restaurant_id == restaurant_id,
                    Product.deleted_at.is_(None),
                    Product.name.ilike(like),
                )
                .limit(limit_per_type)
            )
        ).all()
    )
    customers = list(
        (
            await session.scalars(
                select(Customer)
                .where(
                    Customer.restaurant_id == restaurant_id,
                    or_(Customer.full_name.ilike(like), Customer.phone.ilike(like)),
                )
                .limit(limit_per_type)
            )
        ).all()
    )
    staff = list(
        (
            await session.scalars(
                select(User)
                .where(
                    User.restaurant_id == restaurant_id,
                    User.deleted_at.is_(None),
                    User.full_name.ilike(like),
                )
                .limit(limit_per_type)
            )
        ).all()
    )
    tables = list(
        (
            await session.scalars(
                select(Table)
                .where(Table.restaurant_id == restaurant_id, Table.name.ilike(like))
                .limit(limit_per_type)
            )
        ).all()
    )

    return {
        "orders": [{"id": str(o.id), "order_number": o.order_number, "status": o.status, "total": o.total} for o in orders],
        "products": [{"id": str(p.id), "name": p.name, "price": p.price} for p in products],
        "customers": [{"id": str(c.id), "full_name": c.full_name, "phone": c.phone} for c in customers],
        "staff": [{"id": str(u.id), "full_name": u.full_name, "username": u.username} for u in staff],
        "tables": [{"id": str(t.id), "name": t.name, "zone": t.zone} for t in tables],
    }
