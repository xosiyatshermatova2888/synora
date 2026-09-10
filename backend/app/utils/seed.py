"""Demo/dev seed data. NEVER used in production paths.

Creates the DEMO restaurant with OWNER/ADMIN/CASHIER/WAITER users, a branch,
demo tables, and a small menu (fish/plov/non-alcoholic drinks with modifier
groups) so the API and frontend have realistic data to work with during dev.

Run:
    python -m app.utils.seed

Demo accounts (clearly marked as dev only; change before going live):
    owner@demo.synora  / DemoPass123!
    admin@demo.synora  / DemoPass123!
    cashier@demo.synora / DemoPass123!
    waiter@demo.synora  / DemoPass123!
"""

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models.branch import Branch
from app.models.menu import Category, Modifier, ModifierGroup, Product
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.models.user import User
from app.services.permissions import ensure_system_permissions_and_roles

DEMO_PASSWORD = "DemoPass123!"


async def run() -> None:
    async with SessionLocal() as session:
        roles_by_name = await ensure_system_permissions_and_roles(session)
        await session.flush()

        restaurant = await session.scalar(
            select(Restaurant).where(Restaurant.slug == "demo-restaurant")
        )
        if restaurant is None:
            # Fresh demo workspace.
            restaurant = Restaurant(
                name="Demo Restaurant",
                slug="demo-restaurant",
                timezone="Asia/Tashkent",
                currency="UZS",
            )
            session.add(restaurant)
            await session.flush()
            branch = Branch(restaurant_id=restaurant.id, name="Main Branch")
            session.add(branch)
            await session.flush()

            def make_user(email: str, full_name: str, role_names: list[str]):
                u = User(
                    restaurant_id=restaurant.id,
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    full_name=full_name,
                    roles=[roles_by_name[r] for r in role_names],
                )
                session.add(u)
                return u

            owner = make_user("owner@demo.synora", "Demo Owner", ["OWNER"])
            await session.flush()
            owner.created_by_user_id = owner.id

            make_user("admin@demo.synora", "Demo Admin", ["ADMIN"])
            make_user("cashier@demo.synora", "Demo Cashier", ["CASHIER"])
            make_user("waiter@demo.synora", "Demo Waiter", ["WAITER"])

        else:
            # Existing demo workspace: re-run only fills in whatever is missing
            # (additive, idempotent).
            branch = (await session.scalars(
                select(Branch).where(Branch.restaurant_id == restaurant.id)
            )).first()

        has_menu = await session.scalar(
            select(Category.id).where(Category.restaurant_id == restaurant.id).limit(1)
        )
        if not has_menu:
            # Demo menu (Section 29): categories -> products -> modifiers.
            mains = Category(restaurant_id=restaurant.id, name="Mains", sort_order=1)
            drinks = Category(restaurant_id=restaurant.id, name="Drinks", sort_order=2)
            session.add_all([mains, drinks])
            await session.flush()

            size_group = ModifierGroup(
                restaurant_id=restaurant.id, name="Size", is_required=True,
                min_selections=1, max_selections=1,
            )
            side_group = ModifierGroup(
                restaurant_id=restaurant.id, name="Side", is_required=False,
                min_selections=0, max_selections=2,
            )
            session.add_all([size_group, side_group])
            await session.flush()

            session.add_all([
                Modifier(restaurant_id=restaurant.id, modifier_group_id=size_group.id,
                         name="Small", price=Decimal("0.00"), sort_order=1),
                Modifier(restaurant_id=restaurant.id, modifier_group_id=size_group.id,
                         name="Large", price=Decimal("15000.00"), sort_order=2),
                Modifier(restaurant_id=restaurant.id, modifier_group_id=side_group.id,
                         name="Bread", price=Decimal("3000.00"), sort_order=1),
                Modifier(restaurant_id=restaurant.id, modifier_group_id=side_group.id,
                         name="Salad", price=Decimal("8000.00"), sort_order=2),
            ])

            session.add_all([
                Product(
                    restaurant_id=restaurant.id, category_id=mains.id, name="Osh (Plov)",
                    description="Beef plov with rice and carrots",
                    price=Decimal("45000.00"), cost_price=Decimal("18000.00"),
                    modifier_groups=[size_group, side_group],
                ),
                Product(
                    restaurant_id=restaurant.id, category_id=mains.id, name="Lagman",
                    description="Noodle soup with beef and vegetables",
                    price=Decimal("42000.00"), cost_price=Decimal("15000.00"),
                    modifier_groups=[side_group],
                ),
                Product(
                    restaurant_id=restaurant.id, category_id=drinks.id, name="Green Tea",
                    price=Decimal("5000.00"), cost_price=Decimal("1000.00"),
                ),
                Product(
                    restaurant_id=restaurant.id, category_id=drinks.id, name="Lemonade",
                    price=Decimal("12000.00"), cost_price=Decimal("4000.00"),
                ),
            ])

        has_tables = await session.scalar(
            select(Table.id).where(Table.restaurant_id == restaurant.id).limit(1)
        )
        if not has_tables:
            for name, cap in [("T1", 2), ("T2", 4), ("T3", 4), ("T4", 6), ("T5", 8)]:
                session.add(
                    Table(restaurant_id=restaurant.id, branch_id=branch.id, name=name, capacity=cap)
                )

        await session.commit()
        print("Demo data present: seed is additive and idempotent.")
        print("Logins:")
        for email in [
            "owner@demo.synora",
            "admin@demo.synora",
            "cashier@demo.synora",
            "waiter@demo.synora",
        ]:
            print(f"  {email} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(run())