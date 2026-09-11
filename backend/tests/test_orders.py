"""Order Engine tests (Sections 11/12/13/21 / 32).

Idempotent creation, product/price snapshots, money math via the single pricing
service, the one-and-only status state machine, the table lifecycle, and atomic
rollback on failure.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.order import Order
from tests.conftest import owner_headers, waiter_headers


def _order_payload(world, *, product_id=None, table_id=None, modifiers=None, discount="0.00", quantity=1, source="POS"):
    return {
        "branch_id": str(world.branch_a.id),
        "table_id": str(table_id) if table_id else None,
        "source": source,
        "discount": discount,
        "items": [
            {
                "product_id": str(product_id or world.product_a.id),
                "quantity": quantity,
                "modifiers": modifiers or [],
            }
        ],
    }


def _create(client, world, *, headers=None, idem_key=None, **overrides):
    headers = headers or owner_headers(world)
    if idem_key:
        headers = {**headers, "Idempotency-Key": idem_key}
    payload = _order_payload(world, **overrides)
    return client.post("/api/v1/orders", headers=headers, json=payload)


class TestCreateOrder:
    async def test_create_order_persists_snapshot_and_totals(self, client, world, db):
        res = _create(client, world, table_id=world.table_a.id)
        assert res.status_code == 201, res.text
        order = res.json()
        assert order["status"] == "DRAFT"
        assert order["order_number"] == 1
        assert order["subtotal"] == "45000.00"
        assert order["discount"] == "0.00"
        assert order["tax"] == "0.00"
        assert order["total"] == "45000.00"
        assert order["currency"] == "UZS"
        # Snapshot (Section 13)
        item = order["items"][0]
        assert item["product_name_snapshot"] == "Plov"
        assert item["unit_price"] == "45000.00"

        row = await db.scalar(select(Order).where(Order.id == uuid.UUID(order["id"])))
        assert row is not None
        assert row.order_number == 1

    def test_waiter_order_gets_10pct_service_charge(self, client, world):
        res = _create(client, world, headers=waiter_headers(world), source="WAITER")
        assert res.status_code == 201, res.text
        order = res.json()
        assert order["subtotal"] == "45000.00"
        assert order["service_charge"] == "4500.00"
        assert order["tax"] == "0.00"  # kept separate — never merged with tax
        assert order["total"] == "49500.00"

    def test_pos_order_has_no_service_charge(self, client, world):
        res = _create(client, world, source="POS")
        assert res.status_code == 201, res.text
        order = res.json()
        assert order["service_charge"] == "0.00"
        assert order["total"] == "45000.00"

    def test_order_total_includes_modifier_price(self, client, world):
        res = _create(
            client, world,
            modifiers=[{"modifier_id": str(world.large_mod.id), "quantity": 1}],
        )
        assert res.status_code == 201, res.text
        order = res.json()
        # 45000 + 15000 = 60000
        assert order["subtotal"] == "60000.00"
        assert order["total"] == "60000.00"
        assert order["items"][0]["modifiers"][0]["modifier_name_snapshot"] == "Large"

    def test_multiple_quantity_calculates_correctly(self, client, world):
        res = _create(client, world, quantity=2)
        assert res.status_code == 201
        assert res.json()["total"] == "90000.00"

    def test_order_with_discount(self, client, world):
        res = _create(client, world, discount="5000.00")
        assert res.status_code == 201
        order = res.json()
        assert order["discount"] == "5000.00"
        assert order["total"] == "40000.00"

    def test_create_order_marks_table_occupied(self, client, world):
        _create(client, world, table_id=world.table_a.id)
        res = client.get(
            f"/api/v1/tables/{world.table_a.id}", headers=owner_headers(world)
        )
        assert res.json()["status"] == "OCCUPIED"
        assert res.json()["version"] == 2  # 1 -> claimed -> bumped

    async def test_create_order_rejects_unavailable_product(self, client, world, db):
        from datetime import datetime, timezone

        from app.models.menu import Product

        prod = await db.scalar(select(Product).where(Product.id == world.product_a.id))
        prod.is_available = False
        await db.commit()
        res = _create(client, world)
        assert res.status_code == 422
        await db.rollback()
        prod.is_available = True
        await db.commit()

    async def test_create_order_rejects_disabled_table(self, client, world, db):
        from app.models.table import Table

        tbl = await db.scalar(select(Table).where(Table.id == world.table_a.id))
        tbl.status = "DISABLED"
        await db.commit()
        res = _create(client, world, table_id=world.table_a.id)
        assert res.status_code == 422
        await db.rollback()
        tbl.status = "AVAILABLE"
        await db.commit()


class TestIdempotency:
    async def test_same_key_returns_same_order(self, client, world, db):
        first = _create(client, world, idem_key="key-1234")
        assert first.status_code == 201
        second = _create(client, world, idem_key="key-1234")
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

        count = await db.scalar(
            select(func.count()).select_from(Order).where(
                Order.restaurant_id == world.restaurant_a.id
            )
        )
        assert count == 1

    def test_different_keys_create_two_orders(self, client, world):
        a = _create(client, world, idem_key="key-1")
        b = _create(client, world, idem_key="key-2")
        assert a.json()["id"] != b.json()["id"]

    def test_no_key_always_creates(self, client, world):
        a = _create(client, world)
        b = _create(client, world)
        assert a.json()["id"] != b.json()["id"]


class TestStatusStateMachine:
    def test_draft_to_open_to_completed_to_refunded(self, client, world):
        order_id = _create(client, world).json()["id"]

        opened = client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "OPEN"}
        )
        assert opened.status_code == 200 and opened.json()["status"] == "OPEN"

        completed = client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "COMPLETED"}
        )
        assert completed.status_code == 200 and completed.json()["status"] == "COMPLETED"
        assert completed.json()["completed_at"] is not None

        refunded = client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "REFUNDED"}
        )
        assert refunded.status_code == 200 and refunded.json()["status"] == "REFUNDED"

    def test_invalid_transition_is_rejected(self, client, world):
        order_id = _create(client, world).json()["id"]
        # DRAFT -> COMPLETED is illegal: must go through OPEN.
        res = client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "COMPLETED"}
        )
        assert res.status_code == 422

    def test_terminal_status_has_no_further_transitions(self, client, world):
        order_id = _create(client, world).json()["id"]
        client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "CANCELLED"}
        )
        res = client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "OPEN"}
        )
        assert res.status_code == 422

    def test_unknown_status_is_rejected(self, client, world):
        order_id = _create(client, world).json()["id"]
        res = client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "NOPE"}
        )
        assert res.status_code == 422  # schema pattern fails first

    def test_completing_order_releases_table(self, client, world):
        order_id = _create(client, world, table_id=world.table_a.id).json()["id"]
        client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "OPEN"}
        )
        done = client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "COMPLETED"}
        )
        assert done.status_code == 200
        table = client.get(f"/api/v1/tables/{world.table_a.id}", headers=owner_headers(world)).json()
        assert table["status"] == "AVAILABLE"

    def test_cancelling_order_releases_table(self, client, world):
        order_id = _create(client, world, table_id=world.table_a.id).json()["id"]
        client.patch(
            f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "CANCELLED"}
        )
        table = client.get(f"/api/v1/tables/{world.table_a.id}", headers=owner_headers(world)).json()
        assert table["status"] == "AVAILABLE"


class TestKitchenStatus:
    def test_kitchen_flow_pending_to_new_to_preparing_to_ready(self, client, world):
        order_id = _create(client, world).json()["id"]
        for step in ("NEW", "PREPARING", "READY"):
            res = client.patch(
                f"/api/v1/orders/{order_id}/kitchen-status",
                headers=owner_headers(world),
                json={"kitchen_status": step},
            )
            assert res.status_code == 200, res.text
            assert res.json()["kitchen_status"] == step

    def test_invalid_kitchen_skip_rejected(self, client, world):
        order_id = _create(client, world).json()["id"]
        # PENDING -> READY skips intermediate states.
        res = client.patch(
            f"/api/v1/orders/{order_id}/kitchen-status",
            headers=owner_headers(world),
            json={"kitchen_status": "READY"},
        )
        assert res.status_code == 422


class TestAtomicity:
    async def test_failed_creation_rolls_back_completely(self, client, world, db):
        """A creation failure (bad modifier id) must roll back everything —
        no partially-persisted order."""
        before = await db.scalar(func.count(Order.id)) or 0
        res = client.post(
            "/api/v1/orders",
            headers=owner_headers(world),
            json={
                "branch_id": str(world.branch_a.id),
                "source": "POS",
                "items": [
                    {
                        "product_id": str(world.product_a.id),
                        "quantity": 1,
                        "modifiers": [],
                    },
                    {
                        "product_id": str(world.product_a.id),
                        "quantity": 1,
                        "modifiers": [{"modifier_id": str(world.table_b.id), "quantity": 1}],
                    },
                ],
            },
        )
        assert res.status_code == 404
        after = await db.scalar(func.count(Order.id)) or 0
        assert after == before


class TestOrderListing:
    def test_list_is_paginated(self, client, world):
        for _ in range(3):
            _create(client, world)
        res = client.get("/api/v1/orders?limit=2", headers=owner_headers(world))
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 3
        assert len(body["items"]) == 2
        assert body["limit"] == 2

    def test_active_orders_excludes_completed(self, client, world):
        done = _create(client, world).json()["id"]
        client.patch(
            f"/api/v1/orders/{done}/status", headers=owner_headers(world), json={"status": "OPEN"}
        )
        client.patch(
            f"/api/v1/orders/{done}/status", headers=owner_headers(world), json={"status": "COMPLETED"}
        )
        active = client.get("/api/v1/orders/active", headers=owner_headers(world)).json()
        assert all(o["id"] != done for o in active)