"""Public (unauthenticated) QR-menu API — the one place the API accepts
writes with no auth dependency. Tenant resolution is per-request from the
URL slug; these tests pin down the fail-closed 404 behavior across
restaurant/branch/table mismatches and the end-to-end order-creation path.
"""

from __future__ import annotations

from app.utils import rate_limit


def _order_payload(world, table_id=None):
    return {
        "restaurant_slug": world.restaurant_a.slug,
        "branch_id": str(world.branch_a.id),
        "table_id": str(table_id or world.table_a.id),
        "customer_name": "Test Customer",
        "customer_phone": "+998901112233",
        "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
    }


class TestPublicMenu:
    def test_menu_returns_active_products(self, client, world):
        res = client.get(f"/api/v1/public/menu/{world.restaurant_a.slug}")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["restaurant_name"] == world.restaurant_a.name
        names = [p["name"] for c in body["categories"] for p in c["products"]]
        assert "Plov" in names

    def test_unknown_slug_404s(self, client):
        res = client.get("/api/v1/public/menu/does-not-exist")
        assert res.status_code == 404

    def test_menu_never_leaks_cost_price(self, client, world):
        res = client.get(f"/api/v1/public/menu/{world.restaurant_a.slug}")
        body = res.json()
        for c in body["categories"]:
            for p in c["products"]:
                assert "cost_price" not in p


class TestPublicTables:
    def test_lists_tables_for_branch(self, client, world):
        res = client.get(f"/api/v1/public/tables/{world.restaurant_a.slug}/{world.branch_a.id}")
        assert res.status_code == 200, res.text
        names = [t["name"] for t in res.json()]
        assert "T1" in names

    def test_wrong_restaurant_branch_pair_404s(self, client, world):
        # branch_b belongs to restaurant_b, not restaurant_a.
        res = client.get(f"/api/v1/public/tables/{world.restaurant_a.slug}/{world.branch_b.id}")
        assert res.status_code == 404


class TestPublicOrders:
    def test_creates_order_with_customer_and_kitchen_ticket(self, client, world, db):
        res = client.post("/api/v1/public/orders", json=_order_payload(world))
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["order_number"] >= 1
        assert body["total"] == "45000.00"

    async def test_order_lands_with_qr_source_and_customer(self, client, world, db):
        from sqlalchemy import select
        from app.models.order import Order

        client.post("/api/v1/public/orders", json=_order_payload(world))

        order = (
            await db.scalars(select(Order).where(Order.restaurant_id == world.restaurant_a.id))
        ).first()
        assert order.source == "QR"
        assert order.customer_id is not None
        assert order.kitchen_status == "NEW"

    def test_cross_tenant_table_rejected(self, client, world):
        # table_b belongs to restaurant_b entirely, not restaurant_a/branch_a.
        payload = _order_payload(world, table_id=world.table_b.id)
        res = client.post("/api/v1/public/orders", json=payload)
        assert res.status_code == 404

    async def test_second_customer_with_same_phone_reuses_record(self, client, world, db):
        from sqlalchemy import func, select
        from app.models.customer import Customer

        client.post("/api/v1/public/orders", json=_order_payload(world))
        client.post("/api/v1/public/orders", json=_order_payload(world))

        count = await db.scalar(
            select(func.count(Customer.id)).where(Customer.restaurant_id == world.restaurant_a.id)
        )
        assert count == 1

    def test_rate_limit_trips_after_max_attempts(self, client, world):
        for _ in range(rate_limit.PUBLIC_ORDER_LIMIT_MAX):
            client.post("/api/v1/public/orders", json=_order_payload(world))
        res = client.post("/api/v1/public/orders", json=_order_payload(world))
        assert res.status_code == 429
