"""Audit log — a paper trail for discounts, order cancel/refund, staff role/
access/credential changes, and product price changes. Also confirms a
forced logging failure never blocks the real action (`log_action`'s
fail-soft contract)."""

from __future__ import annotations

from tests.conftest import owner_headers, waiter_headers


def _order_id(client, world):
    res = client.post(
        "/api/v1/orders",
        headers=owner_headers(world),
        json={
            "branch_id": str(world.branch_a.id),
            "table_id": str(world.table_a.id),
            "source": "POS",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


class TestDiscountAudit:
    def test_discount_is_logged(self, client, world):
        order_id = _order_id(client, world)
        client.patch(
            f"/api/v1/orders/{order_id}/discount",
            headers=owner_headers(world),
            json={"discount_type": "PERCENT", "discount": "10"},
        )
        res = client.get("/api/v1/audit-log", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        entries = [e for e in res.json() if e["action"] == "order.discount"]
        assert len(entries) == 1
        assert "10" in entries[0]["summary"]


class TestOrderCancelAudit:
    def test_cancel_is_logged(self, client, world):
        order_id = _order_id(client, world)
        client.patch(f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "OPEN"})
        client.patch(f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "CANCELLED"})
        res = client.get("/api/v1/audit-log?action=order.cancelled", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert len(res.json()) == 1


class TestStaffAudit:
    def test_role_change_is_logged(self, client, world):
        client.patch(
            f"/api/v1/users/{world.waiter_a.id}/role", headers=owner_headers(world), json={"role": "CASHIER"}
        )
        res = client.get("/api/v1/audit-log?action=staff.role_change", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert len(res.json()) == 1
        assert "waiter_a" in res.json()[0]["summary"] or world.waiter_a.username in res.json()[0]["summary"]

    def test_deactivate_is_logged(self, client, world):
        client.patch(
            f"/api/v1/users/{world.waiter_a.id}/active", headers=owner_headers(world), json={"is_active": False}
        )
        res = client.get("/api/v1/audit-log?action=staff.deactivate", headers=owner_headers(world))
        assert len(res.json()) == 1


class TestProductPriceAudit:
    def test_price_change_is_logged(self, client, world):
        client.patch(
            f"/api/v1/menu/products/{world.product_a.id}",
            headers=owner_headers(world),
            json={"price": "50000.00"},
        )
        res = client.get("/api/v1/audit-log?action=product.price_update", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert len(res.json()) == 1

    def test_non_price_edit_not_logged(self, client, world):
        client.patch(
            f"/api/v1/menu/products/{world.product_a.id}",
            headers=owner_headers(world),
            json={"description": "New description"},
        )
        res = client.get("/api/v1/audit-log?action=product.price_update", headers=owner_headers(world))
        assert res.json() == []


class TestAuditLogAccess:
    def test_waiter_cannot_read_audit_log(self, client, world):
        res = client.get("/api/v1/audit-log", headers=waiter_headers(world))
        assert res.status_code == 403


class TestAuditLogFailSoft:
    def test_broken_logging_does_not_block_discount(self, client, world, monkeypatch):
        import app.services.audit as audit_service

        class _BrokenAuditLog:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("simulated audit write failure")

        # Breaks the row construction *inside* log_action's own try/except —
        # this is the real contract (a failed audit WRITE never blocks the
        # action it's recording), not a bypass of log_action's own handling.
        monkeypatch.setattr(audit_service, "AuditLog", _BrokenAuditLog)

        order_id = _order_id(client, world)
        res = client.patch(
            f"/api/v1/orders/{order_id}/discount",
            headers=owner_headers(world),
            json={"discount_type": "FIXED", "discount": "1000"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["discount"] == "1000.00"
