"""Payment + cash shift tests (Sections 14/15/32).

Multiple payments per order, partial-payment state machine, overpayment
rejection, and optimistic-lock-safe cash shift closing.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.models.payment import CashShift, Payment
from app.models.order import Order
from tests.conftest import cashier_headers, owner_headers


def _open_order(client, world, *, headers=None):
    headers = headers or owner_headers(world)
    created = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "branch_id": str(world.branch_a.id),
            "source": "POS",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
        },
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["id"]
    opened = client.patch(
        f"/api/v1/orders/{order_id}/status", headers=headers, json={"status": "OPEN"}
    )
    assert opened.status_code == 200
    return order_id


def _pay(client, world, order_id, amount, *, method="CASH", headers=None):
    headers = headers or owner_headers(world)
    return client.post(
        "/api/v1/payments",
        headers=headers,
        json={"order_id": str(order_id), "amount": str(amount), "method": method},
    )


class TestPayments:
    def test_full_payment_completes_order(self, client, world):
        order_id = _open_order(client, world)
        res = _pay(client, world, order_id, "45000.00")
        assert res.status_code == 201, res.text
        assert res.json()["amount"] == "45000.00"

        order = client.get(f"/api/v1/orders/{order_id}", headers=owner_headers(world)).json()
        assert order["status"] == "COMPLETED"

        payments = client.get(
            f"/api/v1/orders/{order_id}/payments", headers=owner_headers(world)
        ).json()
        assert len(payments) == 1
        assert payments[0]["status"] == "PAID"

    def test_partial_then_full_payment(self, client, world):
        order_id = _open_order(client, world)
        first = _pay(client, world, order_id, "20000.00")
        assert first.status_code == 201
        order = client.get(f"/api/v1/orders/{order_id}", headers=owner_headers(world)).json()
        assert order["status"] == "PARTIALLY_PAID"

        second = _pay(client, world, order_id, "25000.00")
        assert second.status_code == 201
        order = client.get(f"/api/v1/orders/{order_id}", headers=owner_headers(world)).json()
        assert order["status"] == "COMPLETED"

    def test_split_payment_two_methods(self, client, world):
        order_id = _open_order(client, world)
        _pay(client, world, order_id, "20000.00", method="CASH")
        res = _pay(client, world, order_id, "25000.00", method="CARD")
        assert res.status_code == 201
        payments = client.get(
            f"/api/v1/orders/{order_id}/payments", headers=owner_headers(world)
        ).json()
        assert {p["method"] for p in payments} == {"CASH", "CARD"}

    def test_overpayment_rejected(self, client, world):
        order_id = _open_order(client, world)
        res = _pay(client, world, order_id, "99999.00")
        assert res.status_code == 422

    def test_payment_on_completed_order_rejected(self, client, world):
        order_id = _open_order(client, world)
        _pay(client, world, order_id, "45000.00")
        res = _pay(client, world, order_id, "10.00")
        assert res.status_code == 422

    def test_zero_payment_rejected(self, client, world):
        order_id = _open_order(client, world)
        res = _pay(client, world, order_id, "0.00")
        assert res.status_code == 422

    def test_cashier_can_take_payment(self, client, world):
        order_id = _open_order(client, world, headers=cashier_headers(world))
        res = _pay(client, world, order_id, "45000.00", headers=cashier_headers(world))
        assert res.status_code == 201


class TestCashShifts:
    def test_open_and_close_shift(self, client, world, db):
        opened = client.post(
            "/api/v1/cash-shifts/open",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id), "opening_balance": "50000.00"},
        )
        assert opened.status_code == 201, opened.text
        shift = opened.json()
        assert shift["status"] == "OPEN"
        assert shift["opening_balance"] == "50000.00"

        closed = client.post(
            f"/api/v1/cash-shifts/{shift['id']}/close",
            headers=owner_headers(world),
            json={"actual_closing_balance": "50000.00", "version": shift["version"]},
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "CLOSED"
        assert closed.json()["version"] == shift["version"] + 1

    def test_expected_closing_balance_includes_cash_taken(self, client, world):
        opened = client.post(
            "/api/v1/cash-shifts/open",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id), "opening_balance": "0.00"},
        ).json()

        # Sale in CASH after the shift opened.
        order_id = _open_order(client, world)
        _pay(client, world, order_id, "45000.00", method="CASH")

        closed = client.post(
            f"/api/v1/cash-shifts/{opened['id']}/close",
            headers=owner_headers(world),
            json={"actual_closing_balance": "45000.00", "version": opened["version"]},
        ).json()
        assert closed["expected_closing_balance"] == "45000.00"
        assert closed["actual_closing_balance"] == "45000.00"

    async def test_stale_version_close_conflicts(self, client, world, db):
        opened = client.post(
            "/api/v1/cash-shifts/open",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id), "opening_balance": "0.00"},
        ).json()
        # Simulate the racing writer: a concurrent close that already closed the
        # shift would surface as a double-close; to exercise the optimistic-lock
        # branch itself, bump the version while the shift stays OPEN.
        shift_row = await db.scalar(
            select(CashShift).where(CashShift.id == uuid.UUID(opened["id"]))
        )
        shift_row.version += 1
        await db.commit()
        # Close carrying the stale version -> 409.
        res = client.post(
            f"/api/v1/cash-shifts/{opened['id']}/close",
            headers=owner_headers(world),
            json={"actual_closing_balance": "0.00", "version": opened["version"]},
        )
        assert res.status_code == 409

    def test_closing_already_closed_shift_rejected(self, client, world):
        opened = client.post(
            "/api/v1/cash-shifts/open",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id)},
        ).json()
        client.post(
            f"/api/v1/cash-shifts/{opened['id']}/close",
            headers=owner_headers(world),
            json={"actual_closing_balance": "0.00", "version": opened["version"]},
        )
        res = client.post(
            f"/api/v1/cash-shifts/{opened['id']}/close",
            headers=owner_headers(world),
            json={"actual_closing_balance": "0.00", "version": opened["version"] + 1},
        )
        assert res.status_code == 422

    def test_two_open_shifts_per_branch_rejected(self, client, world):
        client.post(
            "/api/v1/cash-shifts/open",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id)},
        )
        res = client.post(
            "/api/v1/cash-shifts/open",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id)},
        )
        assert res.status_code == 422

    async def test_payment_row_is_persisted_restaurant_scoped(self, client, world, db):
        order_id = _open_order(client, world)
        _pay(client, world, order_id, "45000.00")
        row = await db.scalar(
            select(Payment).where(Payment.restaurant_id == world.restaurant_a.id)
        )
        assert row is not None
        assert row.order_id == uuid.UUID(order_id)