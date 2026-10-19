"""Reports/Analytics API — real SQL aggregation over Order/OrderItem/Payment/
Expense, gated by the existing (previously unused) analytics.read permission.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from tests.conftest import owner_headers, waiter_headers


def _complete_order(client, world, *, quantity=1, waiter=False):
    headers = owner_headers(world)
    res = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "branch_id": str(world.branch_a.id),
            "table_id": str(world.table_a.id),
            "source": "POS",
            "items": [{"product_id": str(world.product_a.id), "quantity": quantity, "modifiers": []}],
        },
    )
    assert res.status_code == 201, res.text
    order = res.json()
    client.patch(f"/api/v1/orders/{order['id']}/status", headers=headers, json={"status": "OPEN"})
    pay = client.post(
        "/api/v1/payments",
        headers=headers,
        json={"order_id": order["id"], "amount": order["total"], "method": "CASH"},
    )
    assert pay.status_code == 201, pay.text
    return order


class TestSalesReport:
    def test_sales_series_includes_todays_completed_orders(self, client, world):
        _complete_order(client, world)
        _complete_order(client, world)
        res = client.get("/api/v1/reports/sales", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        body = res.json()
        total_orders = sum(p["order_count"] for p in body["points"])
        assert total_orders == 2

    def test_waiter_cannot_read_reports(self, client, world):
        res = client.get("/api/v1/reports/sales", headers=waiter_headers(world))
        assert res.status_code == 403


class TestProductReport:
    def test_product_report_sums_quantity_and_revenue(self, client, world):
        _complete_order(client, world, quantity=2)
        _complete_order(client, world, quantity=3)
        res = client.get("/api/v1/reports/products", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        rows = res.json()
        assert len(rows) == 1
        assert rows[0]["product_name"] == "Plov"
        assert rows[0]["quantity"] == 5
        assert Decimal(rows[0]["revenue"]) == Decimal("225000.00")  # 5 * 45000


class TestWaiterReport:
    def test_waiter_report_groups_by_waiter(self, client, world):
        _complete_order(client, world)
        res = client.get("/api/v1/reports/waiters", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        rows = res.json()
        assert len(rows) == 1
        assert rows[0]["order_count"] == 1


class TestPaymentReport:
    def test_payment_report_groups_by_method(self, client, world):
        _complete_order(client, world)
        res = client.get("/api/v1/reports/payments", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        rows = res.json()
        assert any(r["method"] == "CASH" for r in rows)


class TestProfitReport:
    def test_profit_is_revenue_minus_expenses(self, client, world):
        _complete_order(client, world)  # 45000 revenue
        client.post(
            "/api/v1/expenses",
            headers=owner_headers(world),
            json={
                "branch_id": str(world.branch_a.id),
                "category": "OTHER",
                "amount": "10000.00",
                "expense_date": date.today().isoformat(),
            },
        )
        res = client.get("/api/v1/reports/profit", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        body = res.json()
        assert Decimal(body["revenue"]) == Decimal("45000.00")
        assert Decimal(body["expenses"]) == Decimal("10000.00")
        assert Decimal(body["profit"]) == Decimal("35000.00")
