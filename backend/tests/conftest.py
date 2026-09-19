"""Shared test fixtures.

Tests run against an isolated FILE-BASED SQLite database (aiosqlite), NOT the
dev PostgreSQL instance (Section 32: "a separate test database, not the dev
database"). Two distinct restaurants are created so the tenant-isolation tests
(Section 5A) can prove separation between tenants - they are meaningless with a
single tenant.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

# MUST be set before importing any `app.*` module so pydantic-settings picks up
# the test DB instead of the committed dev `.env` value.
_TEST_DB = str(Path(__file__).parent / "test_runtime.db")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _TEST_DB.replace("\\", "/")
os.environ["DEBUG"] = "true"
os.environ["REFRESH_COOKIE_SECURE"] = "false"
# Keep the login rate limiter from tripping legitimate test logins; the
# limiter itself has dedicated tests in test_auth.py.
os.environ.setdefault("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "1000")

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.permissions import ALL_PERMISSIONS
from app.core.security import create_access_token, hash_password
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.main import app
from app.models.branch import Branch
from app.models.menu import Category, Modifier, ModifierGroup, Product
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.models.user import User

TEST_PASSWORD = "TestPass123!"


@pytest.fixture(scope="session", autouse=True)
def db_bootstrap():
    """Clean up the test DB file at the end of the session.

    The schema + global permission/role seed are (re)created per-test by the
    `_fresh_db` fixture so no state leaks between tests.
    """
    yield

    async def _teardown():
        await engine.dispose()

    asyncio.run(_teardown())
    try:
        Path(_TEST_DB).unlink()
    except OSError:
        pass


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    """Schema drop/recreate + global permission/role seed for EVERY test.

    Autouse + async so both async and sync tests get clean tables without any
    fixture having to depend on it explicitly.
    """
    from app.services.permissions import ensure_system_permissions_and_roles

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as seed_session:
        await ensure_system_permissions_and_roles(seed_session)
        await seed_session.commit()
    yield


@pytest_asyncio.fixture
async def db():
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _reset_in_process_state():
    """Stateful in-process guards (login/api rate limiters) must not leak
    between tests."""
    from app.utils.rate_limit import login_limiter

    login_limiter._failed.clear()
    yield


@pytest_asyncio.fixture
async def world(db):
    """Two restaurants + users + menu + tables - fixture for tenant tests."""
    from sqlalchemy import select

    from app.models.user import Role

    roles_by_name: dict[str, Role] = {}
    for role in (
        await db.scalars(
            select(Role).where(Role.is_system_role.is_(True), Role.restaurant_id.is_(None))
        )
    ).all():
        roles_by_name[role.name] = role

    alpha = Restaurant(name="Alpha Grill", slug="alpha-grill", currency="UZS", timezone="Asia/Tashkent")
    beta = Restaurant(name="Beta Cafe", slug="beta-cafe", currency="UZS", timezone="Asia/Tashkent")
    db.add_all([alpha, beta])
    await db.flush()

    branch_a = Branch(restaurant_id=alpha.id, name="Main Branch")
    branch_b = Branch(restaurant_id=beta.id, name="Main Branch")
    db.add_all([branch_a, branch_b])
    await db.flush()

    def make_user(restaurant_id, username, full_name, role_names):
        u = User(
            restaurant_id=restaurant_id,
            username=username,
            password_hash=hash_password(TEST_PASSWORD),
            full_name=full_name,
            roles=[roles_by_name[n] for n in role_names],
        )
        db.add(u)
        return u

    owner_a = make_user(alpha.id, "owner_a@synora.io", "Alice Owner", ["OWNER"])
    cashier_a = make_user(alpha.id, "cashier_a@synora.io", "Charlie Cashier", ["CASHIER"])
    waiter_a = make_user(alpha.id, "waiter_a@synora.io", "Wanda Waiter", ["WAITER"])
    kitchen_a = make_user(alpha.id, "kitchen_a@synora.io", "Karl Kitchen", ["KITCHEN"])
    owner_b = make_user(beta.id, "owner_b@synora.io", "Bob Owner", ["OWNER"])
    waiter_b = make_user(beta.id, "waiter_b@synora.io", "Victor Waiter", ["WAITER"])
    await db.flush()
    owner_a.created_by_user_id = owner_a.id
    owner_b.created_by_user_id = owner_b.id

    cat_a = Category(restaurant_id=alpha.id, name="Mains", sort_order=1)
    cat_b = Category(restaurant_id=beta.id, name="Drinks", sort_order=1)
    db.add_all([cat_a, cat_b])
    await db.flush()

    size_group = ModifierGroup(
        restaurant_id=alpha.id, name="Size", is_required=True,
        min_selections=1, max_selections=1,
    )
    side_group = ModifierGroup(
        restaurant_id=alpha.id, name="Side", is_required=False,
        min_selections=0, max_selections=2,
    )
    db.add_all([size_group, side_group])
    await db.flush()

    large_mod = Modifier(
        restaurant_id=alpha.id, modifier_group_id=size_group.id,
        name="Large", price=Decimal("15000.00"), sort_order=1,
    )
    bread_mod = Modifier(
        restaurant_id=alpha.id, modifier_group_id=side_group.id,
        name="Bread", price=Decimal("3000.00"), sort_order=1,
    )
    db.add_all([large_mod, bread_mod])

    prod_a = Product(
        restaurant_id=alpha.id,
        category_id=cat_a.id,
        name="Plov",
        price=Decimal("45000.00"),
        cost_price=Decimal("18000.00"),
        modifier_groups=[size_group, side_group],
    )
    prod_b = Product(
        restaurant_id=beta.id,
        category_id=cat_b.id,
        name="Cola",
        price=Decimal("12000.00"),
        cost_price=Decimal("7000.00"),
    )
    db.add_all([prod_a, prod_b])

    table_a = Table(restaurant_id=alpha.id, branch_id=branch_a.id, name="T1", capacity=4)
    table_a2 = Table(restaurant_id=alpha.id, branch_id=branch_a.id, name="T2", capacity=2)
    table_b = Table(restaurant_id=beta.id, branch_id=branch_b.id, name="T1", capacity=4)
    db.add_all([table_a, table_a2, table_b])

    await db.commit()
    for u in (owner_a, cashier_a, waiter_a, kitchen_a, owner_b, waiter_b):
        await db.refresh(u)

    return SimpleNamespace(
        restaurant_a=alpha,
        restaurant_b=beta,
        branch_a=branch_a,
        branch_b=branch_b,
        owner_a=owner_a,
        cashier_a=cashier_a,
        waiter_a=waiter_a,
        kitchen_a=kitchen_a,
        owner_b=owner_b,
        waiter_b=waiter_b,
        category_a=cat_a,
        category_b=cat_b,
        product_a=prod_a,
        product_b=prod_b,
        size_group=size_group,
        side_group=side_group,
        large_mod=large_mod,
        bread_mod=bread_mod,
        table_a=table_a,
        table_a2=table_a2,
        table_b=table_b,
    )


@pytest.fixture
def client():
    """Sync HTTP client against the ASGI app (no lifespan startup - the
    bootstrapping happened in the `_fresh_db` autouse fixture)."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Token / header helpers
# ---------------------------------------------------------------------------
def auth_headers(user_id: uuid.UUID, restaurant_id: uuid.UUID, permissions: list[str]) -> dict[str, str]:
    token = create_access_token(
        subject=str(user_id),
        restaurant_id=str(restaurant_id),
        permission_codes=permissions,
    )
    return {"Authorization": f"Bearer {token}"}


def owner_headers(world):
    return auth_headers(world.owner_a.id, world.restaurant_a.id, list(ALL_PERMISSIONS))


def waiter_headers(world):
    from app.core.permissions import ROLE_TEMPLATES

    return auth_headers(world.waiter_a.id, world.restaurant_a.id, ROLE_TEMPLATES["WAITER"])


def cashier_headers(world):
    from app.core.permissions import ROLE_TEMPLATES

    return auth_headers(world.cashier_a.id, world.restaurant_a.id, ROLE_TEMPLATES["CASHIER"])


def kitchen_headers(world):
    from app.core.permissions import ROLE_TEMPLATES

    return auth_headers(world.kitchen_a.id, world.restaurant_a.id, ROLE_TEMPLATES["KITCHEN"])


def headers_for_restaurant_b_waiter(world):
    from app.core.permissions import ROLE_TEMPLATES

    return auth_headers(world.waiter_b.id, world.restaurant_b.id, ROLE_TEMPLATES["WAITER"])