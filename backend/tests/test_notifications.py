"""Notification center — a durable row (REST) plus a live WebSocket push,
written together by `services/notifications.py::create_notification`. These
tests cover all 4 trigger points, the list/mark-read endpoints, tenant
isolation, and confirm the shared WS auth helper (`app/websocket/auth.py`)
works identically for `/ws/notifications` as it already does for
`/ws/kitchen` (see `test_kitchen.py::TestKitchenWebSocket`).
"""

from __future__ import annotations

import pytest
from starlette.testclient import WebSocketDisconnect

from app.core.permissions import ALL_PERMISSIONS
from app.core.security import create_access_token
from tests.conftest import auth_headers, owner_headers


def _order_id(client, world, table_id=None):
    res = client.post(
        "/api/v1/orders",
        headers=owner_headers(world),
        json={
            "branch_id": str(world.branch_a.id),
            "table_id": str(table_id or world.table_a.id),
            "source": "POS",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _place_qr_order(client, world):
    res = client.post(
        "/api/v1/public/orders",
        json={
            "restaurant_slug": world.restaurant_a.slug,
            "branch_id": str(world.branch_a.id),
            "table_id": str(world.table_a.id),
            "customer_name": "Test Customer",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
        },
    )
    assert res.status_code == 201, res.text


class TestNewOrderNotification:
    def test_qr_order_creates_notification(self, client, world):
        _place_qr_order(client, world)
        res = client.get("/api/v1/notifications", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        types = [n["type"] for n in res.json()]
        assert "NEW_ORDER" in types

    def test_pos_order_does_not_notify(self, client, world):
        _order_id(client, world)
        res = client.get("/api/v1/notifications", headers=owner_headers(world))
        types = [n["type"] for n in res.json()]
        assert "NEW_ORDER" not in types


class TestLowStockNotification:
    def test_crossing_minimum_notifies_once(self, client, world):
        item = client.post(
            "/api/v1/inventory-items",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id), "name": "Pomidor", "unit": "kg", "minimum_quantity": "5.000"},
        ).json()
        client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "IN", "quantity": "10.000"},
        )
        # Not low yet (10 > 5) -> no notification.
        no_low_yet = client.get("/api/v1/notifications", headers=owner_headers(world)).json()
        assert not any(n["type"] == "LOW_STOCK" for n in no_low_yet)

        client.post(
            f"/api/v1/inventory-items/{item['id']}/transactions",
            headers=owner_headers(world),
            json={"type": "OUT", "quantity": "8.000"},  # 10 - 8 = 2, below minimum(5)
        )
        res = client.get("/api/v1/notifications", headers=owner_headers(world))
        low_stock = [n for n in res.json() if n["type"] == "LOW_STOCK"]
        assert len(low_stock) == 1


class TestPaymentNotification:
    def test_payment_creates_notification(self, client, world):
        order_id = _order_id(client, world)
        client.patch(f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "OPEN"})
        client.post(
            "/api/v1/payments",
            headers=owner_headers(world),
            json={"order_id": order_id, "amount": "45000.00", "method": "CASH"},
        )
        res = client.get("/api/v1/notifications", headers=owner_headers(world))
        assert any(n["type"] == "PAYMENT" for n in res.json())


class TestOrderCancelledNotification:
    def test_cancel_creates_notification(self, client, world):
        order_id = _order_id(client, world)
        client.patch(f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "OPEN"})
        client.patch(f"/api/v1/orders/{order_id}/status", headers=owner_headers(world), json={"status": "CANCELLED"})
        res = client.get("/api/v1/notifications", headers=owner_headers(world))
        assert any(n["type"] == "ORDER_CANCELLED" for n in res.json())


class TestNotificationEndpoints:
    def test_tenant_isolation(self, client, world):
        _place_qr_order(client, world)
        res = client.get("/api/v1/notifications", headers=owner_headers(world))
        # world.restaurant_b's owner must never see restaurant_a's notifications.
        b_headers = auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))
        res_b = client.get("/api/v1/notifications", headers=b_headers)
        assert res_b.status_code == 200
        assert res_b.json() == []
        assert len(res.json()) >= 1

    def test_mark_read(self, client, world):
        _place_qr_order(client, world)
        notif = client.get("/api/v1/notifications", headers=owner_headers(world)).json()[0]
        assert notif["is_read"] is False
        res = client.patch(f"/api/v1/notifications/{notif['id']}/read", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert res.json()["is_read"] is True

    def test_mark_all_read(self, client, world):
        _place_qr_order(client, world)
        res = client.post("/api/v1/notifications/mark-all-read", headers=owner_headers(world))
        assert res.status_code == 204
        notifications = client.get("/api/v1/notifications", headers=owner_headers(world)).json()
        assert all(n["is_read"] for n in notifications)


class TestNotificationsWebSocket:
    def _ws_url(self, token, branch=None):
        url = f"/api/v1/ws/notifications?token={token}"
        if branch is not None:
            url += f"&branch_id={branch}"
        return url

    def test_event_delivered_live(self, client, world):
        token = create_access_token(
            subject=str(world.owner_a.id),
            restaurant_id=str(world.restaurant_a.id),
            permission_codes=list(ALL_PERMISSIONS),
        )
        with client.websocket_connect(self._ws_url(token, world.branch_a.id)) as ws:
            _place_qr_order(client, world)
            # A QR order also broadcasts a kitchen-ticket event on the same
            # (restaurant, branch) channel (Section 3/Phase K) — both this
            # socket and `/ws/kitchen` share the connection registry, so
            # read past it rather than assume the notification is first.
            notification = None
            for _ in range(3):
                msg = ws.receive_json()
                if msg.get("event") == "notification":
                    notification = msg["notification"]
                    break
            assert notification is not None, "no notification event received"
            assert notification["type"] == "NEW_ORDER"

    def test_invalid_token_is_rejected(self, client):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/ws/notifications?token=not-a-real-token"):
                pass
