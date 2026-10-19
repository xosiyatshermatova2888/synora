"""Customer/CRM API — read-only from the dashboard; rows are created by the
public QR order-creation path (see test_public.py). These tests cover the
list/detail endpoints and the computed-stats math."""

from __future__ import annotations

from tests.conftest import owner_headers, waiter_headers


def _place_qr_order(client, world, phone="+998901112233", quantity=1):
    return client.post(
        "/api/v1/public/orders",
        json={
            "restaurant_slug": world.restaurant_a.slug,
            "branch_id": str(world.branch_a.id),
            "table_id": str(world.table_a.id),
            "customer_name": "Nodira",
            "customer_phone": phone,
            "items": [{"product_id": str(world.product_a.id), "quantity": quantity, "modifiers": []}],
        },
    )


class TestListCustomers:
    def test_owner_lists_customers(self, client, world):
        _place_qr_order(client, world)
        res = client.get("/api/v1/customers", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert any(c["phone"] == "+998901112233" for c in res.json())

    def test_search_by_phone(self, client, world):
        _place_qr_order(client, world, phone="+998900000001")
        res = client.get("/api/v1/customers?search=0000001", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert len(res.json()) == 1

    def test_waiter_cannot_list_customers(self, client, world):
        res = client.get("/api/v1/customers", headers=waiter_headers(world))
        assert res.status_code == 403


class TestCustomerDetail:
    def test_detail_shows_recent_orders(self, client, world):
        _place_qr_order(client, world, phone="+998907778899")
        customers = client.get("/api/v1/customers", headers=owner_headers(world)).json()
        customer = next(c for c in customers if c["phone"] == "+998907778899")

        res = client.get(f"/api/v1/customers/{customer['id']}", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["customer"]["phone"] == "+998907778899"
        # The QR order starts DRAFT, so it shows in recent_orders but not yet
        # in total_orders/total_spent (those only count COMPLETED orders).
        assert len(body["recent_orders"]) == 1
        assert body["total_orders"] == 0

    async def test_completed_order_counts_toward_totals(self, client, world, db):
        _place_qr_order(client, world, phone="+998905554433")
        from sqlalchemy import select
        from app.models.order import Order

        order = (
            await db.scalars(select(Order).where(Order.restaurant_id == world.restaurant_a.id))
        ).first()
        client.patch(
            f"/api/v1/orders/{order.id}/status", headers=owner_headers(world), json={"status": "OPEN"}
        )
        client.post(
            "/api/v1/payments",
            headers=owner_headers(world),
            json={"order_id": str(order.id), "amount": str(order.total), "method": "CASH"},
        )

        customers = client.get("/api/v1/customers", headers=owner_headers(world)).json()
        customer = next(c for c in customers if c["phone"] == "+998905554433")
        body = client.get(f"/api/v1/customers/{customer['id']}", headers=owner_headers(world)).json()
        assert body["total_orders"] == 1
        assert body["total_spent"] == str(order.total)
        assert "Plov" in body["favorite_products"]
