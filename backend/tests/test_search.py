"""Global search — tenant-scoped `ilike` lookups across orders, products,
customers, staff, and tables (Section 21)."""

from __future__ import annotations

from tests.conftest import owner_headers, waiter_headers


class TestGlobalSearch:
    def test_finds_product_by_name(self, client, world):
        res = client.get("/api/v1/search?q=Plov", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        names = [p["name"] for p in res.json()["products"]]
        assert "Plov" in names

    def test_finds_table_by_name(self, client, world):
        res = client.get("/api/v1/search?q=T1", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        names = [t["name"] for t in res.json()["tables"]]
        assert "T1" in names

    def test_finds_staff_by_name(self, client, world):
        res = client.get("/api/v1/search?q=Wanda", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        names = [s["full_name"] for s in res.json()["staff"]]
        assert "Wanda Waiter" in names

    def test_finds_order_by_number(self, client, world):
        order = client.post(
            "/api/v1/orders",
            headers=owner_headers(world),
            json={
                "branch_id": str(world.branch_a.id),
                "table_id": str(world.table_a.id),
                "source": "POS",
                "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            },
        ).json()
        res = client.get(f"/api/v1/search?q={order['order_number']}", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        numbers = [o["order_number"] for o in res.json()["orders"]]
        assert order["order_number"] in numbers

    def test_never_returns_other_tenant_results(self, client, world):
        # world.product_b belongs to restaurant_b ("Cola"); restaurant_a's
        # owner searching for it must get nothing.
        res = client.get("/api/v1/search?q=Cola", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert res.json()["products"] == []

    def test_waiter_can_search(self, client, world):
        # orders.read is broad enough to cover WAITER too.
        res = client.get("/api/v1/search?q=Plov", headers=waiter_headers(world))
        assert res.status_code == 200, res.text
