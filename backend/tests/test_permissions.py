"""RBAC tests (Section 7A / 32).

`require_permission` is the ONLY place authorization lives (single code path),
so the tests pin down that waiters/kitchen/cashiers can do exactly what their
role grants and nothing more — kitchen/waiter must be blocked from finance.
"""

from __future__ import annotations

import pytest

from tests.conftest import (
    cashier_headers,
    kitchen_headers,
    owner_headers,
    waiter_headers,
)


class TestWaiterRole:
    def test_waiter_can_create_order(self, client, world):
        res = client.post(
            "/api/v1/orders",
            headers=waiter_headers(world),
            json={
                "branch_id": str(world.branch_a.id),
                "source": "WAITER",
                "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            },
        )
        assert res.status_code == 201, res.text

    def test_waiter_cannot_create_branch(self, client, world):
        res = client.post(
            "/api/v1/branches", headers=waiter_headers(world), json={"name": "Hack Branch"}
        )
        assert res.status_code == 403

    def test_waiter_cannot_read_menu(self, client, world):
        res = client.get("/api/v1/menu/categories", headers=waiter_headers(world))
        assert res.status_code == 403

    def test_waiter_cannot_create_category(self, client, world):
        res = client.post(
            "/api/v1/menu/categories", headers=waiter_headers(world), json={"name": "Hack Cat"}
        )
        assert res.status_code == 403

    def test_waiter_cannot_access_finance(self, client, world):
        assert client.get("/api/v1/cash-shifts", headers=waiter_headers(world)).status_code == 403
        assert client.post(
            "/api/v1/cash-shifts/open",
            headers=waiter_headers(world),
            json={"branch_id": str(world.branch_a.id)},
        ).status_code == 403

    def test_waiter_has_no_users_manage(self, client, world):
        res = client.post(
            "/api/v1/tables", headers=waiter_headers(world),
            json={"branch_id": str(world.branch_a.id), "name": "T99", "capacity": 4},
        )
        assert res.status_code == 403


class TestKitchenRole:
    def test_kitchen_can_read_orders(self, client, world):
        res = client.get("/api/v1/orders", headers=kitchen_headers(world))
        assert res.status_code == 200

    def test_kitchen_can_update_kitchen_status(self, client, world):
        created = client.post(
            "/api/v1/orders",
            headers=owner_headers(world),
            json={
                "branch_id": str(world.branch_a.id),
                "source": "POS",
                "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            },
        )
        order_id = created.json()["id"]
        res = client.patch(
            f"/api/v1/orders/{order_id}/kitchen-status",
            headers=kitchen_headers(world),
            json={"kitchen_status": "NEW"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["kitchen_status"] == "NEW"

    def test_kitchen_blocked_from_finance(self, client, world):
        res = client.get("/api/v1/cash-shifts", headers=kitchen_headers(world))
        assert res.status_code == 403

    def test_kitchen_blocked_from_menu_management(self, client, world):
        res = client.post(
            "/api/v1/menu/categories", headers=kitchen_headers(world), json={"name": "Hack"}
        )
        assert res.status_code == 403


class TestCashierRole:
    def test_cashier_can_read_cash_shifts(self, client, world):
        res = client.get("/api/v1/cash-shifts", headers=cashier_headers(world))
        assert res.status_code == 200

    def test_cashier_cannot_open_cash_shift(self, client, world):
        res = client.post(
            "/api/v1/cash-shifts/open",
            headers=cashier_headers(world),
            json={"branch_id": str(world.branch_a.id)},
        )
        assert res.status_code == 403  # finance.manage required

    def test_cashier_cannot_manage_users_or_tables(self, client, world):
        res = client.post(
            "/api/v1/tables", headers=cashier_headers(world),
            json={"branch_id": str(world.branch_a.id), "name": "T99", "capacity": 4},
        )
        assert res.status_code == 403


class TestOwnerRole:
    def test_owner_can_everything(self, client, world):
        assert client.get("/api/v1/menu/categories", headers=owner_headers(world)).status_code == 200
        assert client.get("/api/v1/cash-shifts", headers=owner_headers(world)).status_code == 200

    def test_owner_can_manage_branches_and_tables(self, client, world):
        branch = client.post(
            "/api/v1/branches", headers=owner_headers(world), json={"name": "Branch 2"}
        )
        assert branch.status_code == 201
        table = client.post(
            "/api/v1/tables", headers=owner_headers(world),
            json={"branch_id": str(branch.json()["id"]), "name": "Z1", "capacity": 6},
        )
        assert table.status_code == 201


class TestUnauthenticated:
    def test_all_protected_routes_reject_anonymous(self, client):
        for path in (
            "/api/v1/auth/me",
            "/api/v1/restaurant/me",
            "/api/v1/branches",
            "/api/v1/menu/categories",
            "/api/v1/tables",
            "/api/v1/orders",
        ):
            assert client.get(path).status_code == 401, path

    def test_permission_dependency_requires_valid_token(self, client):
        res = client.get("/api/v1/cash-shifts", headers={"Authorization": "Bearer nope"})
        assert res.status_code == 401