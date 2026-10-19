"""Inventory API — stock items + kirim/chiqim/adjustment transactions.

`record_transaction` (app/services/inventory.py) is the only place
`InventoryItem.quantity` is written; these tests pin down its math and the
low-stock flag, plus the `inventory.read`/`inventory.manage` RBAC gate.
"""

from __future__ import annotations

from tests.conftest import owner_headers, waiter_headers


def _create_item(client, world, minimum="5.000"):
    res = client.post(
        "/api/v1/inventory-items",
        headers=owner_headers(world),
        json={
            "branch_id": str(world.branch_a.id),
            "name": "Pomidor",
            "unit": "kg",
            "minimum_quantity": minimum,
            "cost_per_unit": "12000.00",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


class TestInventoryItems:
    def test_create_item_starts_at_zero_quantity(self, client, world):
        item = _create_item(client, world)
        assert item["quantity"] == "0.000"
        assert item["is_low_stock"] is True  # 0 <= minimum(5)

    def test_waiter_cannot_manage_inventory(self, client, world):
        res = client.post(
            "/api/v1/inventory-items",
            headers=waiter_headers(world),
            json={"branch_id": str(world.branch_a.id), "name": "X", "unit": "kg"},
        )
        assert res.status_code == 403


class TestInventoryTransactions:
    def test_in_transaction_increases_quantity(self, client, world):
        item = _create_item(client, world)
        res = client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "IN", "quantity": "10.000", "reason": "delivery"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["quantity"] == "10.000"
        assert res.json()["is_low_stock"] is False  # 10 > minimum(5)

    def test_out_transaction_decreases_quantity(self, client, world):
        item = _create_item(client, world)
        client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "IN", "quantity": "10.000"},
        )
        res = client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "OUT", "quantity": "7.000", "reason": "used in kitchen"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["quantity"] == "3.000"
        assert res.json()["is_low_stock"] is True  # 3 <= minimum(5)

    def test_out_transaction_rejected_below_zero(self, client, world):
        item = _create_item(client, world)
        res = client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "OUT", "quantity": "1.000"},
        )
        assert res.status_code == 422

    def test_adjustment_sets_absolute_quantity(self, client, world):
        item = _create_item(client, world)
        client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "IN", "quantity": "10.000"},
        )
        res = client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "ADJUSTMENT", "quantity": "6.500", "reason": "stock count"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["quantity"] == "6.500"

    def test_transaction_history_is_recorded(self, client, world):
        item = _create_item(client, world)
        client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "IN", "quantity": "10.000"},
        )
        client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "OUT", "quantity": "2.000"},
        )
        res = client.get(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
        )
        assert res.status_code == 200, res.text
        assert len(res.json()) == 2
