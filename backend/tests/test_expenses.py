"""Expense CRUD API — gated by the existing finance.read/finance.manage
permissions (same convention as Payments, no new permission codes)."""

from __future__ import annotations

from tests.conftest import owner_headers, waiter_headers


def _create_expense(client, world, category="RENT", amount="500000.00", expense_date="2026-09-01"):
    res = client.post(
        "/api/v1/expenses",
        headers=owner_headers(world),
        json={
            "branch_id": str(world.branch_a.id),
            "category": category,
            "amount": amount,
            "expense_date": expense_date,
            "description": "test expense",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


class TestExpenseCrud:
    def test_owner_creates_expense(self, client, world):
        expense = _create_expense(client, world)
        assert expense["category"] == "RENT"
        assert expense["amount"] == "500000.00"

    def test_waiter_cannot_create_expense(self, client, world):
        res = client.post(
            "/api/v1/expenses",
            headers=waiter_headers(world),
            json={
                "branch_id": str(world.branch_a.id),
                "category": "OTHER",
                "amount": "1000.00",
                "expense_date": "2026-09-01",
            },
        )
        assert res.status_code == 403

    def test_list_filters_by_category(self, client, world):
        _create_expense(client, world, category="RENT")
        _create_expense(client, world, category="UTILITIES")
        res = client.get(
            "/api/v1/expenses?category=UTILITIES",
            headers=owner_headers(world),
        )
        assert res.status_code == 200, res.text
        assert all(e["category"] == "UTILITIES" for e in res.json())

    def test_update_expense(self, client, world):
        expense = _create_expense(client, world)
        res = client.patch(
            f"/api/v1/expenses/{expense['id']}",
            headers=owner_headers(world),
            json={"amount": "600000.00"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["amount"] == "600000.00"

    def test_delete_expense(self, client, world):
        expense = _create_expense(client, world)
        res = client.delete(f"/api/v1/expenses/{expense['id']}", headers=owner_headers(world))
        assert res.status_code == 204
        listed = client.get("/api/v1/expenses", headers=owner_headers(world)).json()
        assert all(e["id"] != expense["id"] for e in listed)
