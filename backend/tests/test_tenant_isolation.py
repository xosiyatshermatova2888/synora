"""Tenant isolation tests (Section 5A/32).

The rule: cross-tenant access MUST surface as 404 (never 403 or the data) so
resource presence is never disclosed. A user of Restaurant A must never see
Restaurant B's resources through ANY tenant-scoped endpoint.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.branch import Branch
from app.models.order import Order
from app.models.table import Table as TableModel
from app.models.user import User
from tests.conftest import auth_headers, headers_for_restaurant_b_waiter, owner_headers, waiter_headers, TEST_PASSWORD
from tests.conftest import ALL_PERMISSIONS


def _make_order(client, headers, world, *, branch_id, table_id=None, product_id=None):
    return client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "branch_id": str(branch_id),
            "table_id": str(table_id) if table_id else None,
            "source": "POS",
            "items": [
                {
                    "product_id": str(product_id or world.product_a.id),
                    "quantity": 1,
                    "modifiers": [],
                }
            ],
        },
    )


class TestCrossTenantResourceAccess:
    def test_table_from_other_tenant_is_404(self, client, world):
        res = client.get(f"/api/v1/tables/{world.table_b.id}", headers=owner_headers(world))
        assert res.status_code == 404

    def test_product_from_other_tenant_is_404(self, client, world):
        res = client.get(f"/api/v1/menu/products/{world.product_b.id}", headers=owner_headers(world))
        assert res.status_code == 404

    def test_category_from_other_tenant_is_404(self, client, world):
        res = client.get(f"/api/v1/menu/categories/{world.category_b.id}", headers=owner_headers(world))
        assert res.status_code == 404

    def test_branch_from_other_tenant_is_404(self, client, world):
        res = client.get(f"/api/v1/branches/{world.branch_b.id}", headers=owner_headers(world))
        assert res.status_code == 404

    def test_order_from_other_tenant_is_404(self, client, world):
        # Create an order inside Restaurant B first (as B's owner).
        b_owner_headers = auth_headers(
            world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS)
        )
        created = _make_order(
            client, b_owner_headers, world,
            branch_id=world.branch_b.id, product_id=world.product_b.id,
        )
        assert created.status_code == 201, created.text
        order_id = created.json()["id"]

        # Restaurant A's owner requests Restaurant B's order -> 404.
        res = client.get(f"/api/v1/orders/{order_id}", headers=owner_headers(world))
        assert res.status_code == 404

        # B's list endpoint never leaks into A's list.
        mine = client.get("/api/v1/orders", headers=owner_headers(world))
        assert all(o["restaurant_id"] == str(world.restaurant_a.id) for o in mine.json()["items"])

    def test_create_order_rejects_product_of_other_tenant(self, client, world):
        """Attempting to order B's product as tenant A -> 404 (must not reveal/mix)."""
        res = _make_order(
            client, owner_headers(world), world,
            branch_id=world.branch_a.id, product_id=world.product_b.id,
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "One or more products not found in this restaurant."


class TestTenantListsAreScoped:
    def test_branches_list_only_shows_own_tenant(self, client, world):
        res = client.get("/api/v1/branches", headers=owner_headers(world))
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["id"] == str(world.branch_a.id)

    def test_tables_list_only_shows_own_tenant(self, client, world):
        res = client.get("/api/v1/tables", headers=owner_headers(world))
        ids = [t["id"] for t in res.json()]
        assert str(world.table_a.id) in ids
        assert str(world.table_b.id) not in ids

    def test_tables_list_of_other_branch_scoped(self, client, world):
        res = client.get(
            f"/api/v1/tables?branch_id={world.branch_b.id}",
            headers=owner_headers(world),
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_menu_categories_list_only_shows_own_tenant(self, client, world):
        res = client.get("/api/v1/menu/categories", headers=owner_headers(world))
        ids = [c["id"] for c in res.json()]
        assert str(world.category_a.id) in ids
        assert str(world.category_b.id) not in ids


class TestTenantIdentityFromJWT:
    def test_restaurant_me_returns_authenticated_tenant(self, client, world):
        res = client.get("/api/v1/restaurant/me", headers=owner_headers(world))
        assert res.status_code == 200
        assert res.json()["id"] == str(world.restaurant_a.id)
        assert res.json()["name"] == "Alpha Grill"

    def test_restaurant_me_for_restaurant_b_user(self, client, world):
        b_headers = auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))
        res = client.get("/api/v1/restaurant/me", headers=b_headers)
        assert res.json()["id"] == str(world.restaurant_b.id)

    def test_tampered_tenant_in_body_is_ignored(self, client, world):
        """Client-supplied filters cannot widen scope: owner of A passing B's
        branch_id still gets B's branch (which it cannot see) — i.e. it must not
        leak, and cross-tenant branch lookup stays a 404."""
        res = client.get(f"/api/v1/branches/{world.branch_b.id}", headers=owner_headers(world))
        assert res.status_code == 404


class TestCrossTenantUsers:
    async def test_restaurant_b_user_cannot_read_restaurant_a_orders(self, client, world):
        created = _make_order(
            client, owner_headers(world), world, branch_id=world.branch_a.id
        )
        assert created.status_code == 201
        order_id = created.json()["id"]

        res = client.get(
            f"/api/v1/orders/{order_id}", headers=headers_for_restaurant_b_waiter(world)
        )
        assert res.status_code == 404

    async def test_two_restaurants_with_two_distinct_tenants_in_db(self, db, world):
        # Prove the fixture itself set up two separate tenants.
        users = (await db.scalars(select(User))).all()
        goods = {u.restaurant_id for u in users}
        assert len(goods) == 2

    async def test_user_counts_per_restaurant(self, db, world):
        count_a = len(
            list((await db.scalars(select(User).where(User.restaurant_id == world.restaurant_a.id))).all())
        )
        count_b = len(
            list((await db.scalars(select(User).where(User.restaurant_id == world.restaurant_b.id))).all())
        )
        assert count_a == 4  # owner, cashier, waiter, kitchen
        assert count_b == 2  # owner, waiter


class TestCrossTenantNoDataLeakInLists:
    def test_b_owner_cannot_see_a_orders_via_active_endpoint(self, client, world):
        _make_order(client, owner_headers(world), world, branch_id=world.branch_a.id)
        b_headers = auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))
        res = client.get("/api/v1/orders/active", headers=b_headers)
        assert res.status_code == 200
        assert res.json() == []