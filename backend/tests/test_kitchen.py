"""Kitchen module tests (Phase K).

Covers: ticket lifecycle driven by the order engine (created on PENDING->NEW,
mirroring NEW -> PREPARING -> READY), station CRUD + permissions, cross-tenant
isolation, and the authenticated WebSocket fan-out (event delivery on the owning
tenant + strict isolation from other tenants + invalid-token rejection).
"""

from __future__ import annotations

import uuid

import pytest
from starlette.testclient import WebSocketDisconnect

from app.core.permissions import ALL_PERMISSIONS, ROLE_TEMPLATES
from app.core.security import create_access_token
from tests.conftest import (
    auth_headers,
    kitchen_headers,
    owner_headers,
    waiter_headers,
)

TICKETS_URL = "/api/v1/kitchen/tickets"


def _create(client, world, *, headers=None):
    headers = headers or owner_headers(world)
    return client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "branch_id": str(world.branch_a.id),
            "source": "POS",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            "table_id": str(world.table_a.id),
        },
    )


def _send_to_kitchen(client, world, order_id, *, headers=None):
    headers = headers or owner_headers(world)
    return client.patch(
        f"/api/v1/orders/{order_id}/kitchen-status",
        headers=headers,
        json={"kitchen_status": "NEW"},
    )


def _tickets(client, world, *, branch_id=None, headers=None):
    branch_id = branch_id or world.branch_a.id
    return client.get(
        f"{TICKETS_URL}?branch_id={branch_id}",
        headers=headers or owner_headers(world),
    )


def _first_ticket(client, world, **kw):
    res = _tickets(client, world, **kw)
    assert res.status_code == 200, res.text
    tickets = res.json()
    assert len(tickets) == 1, tickets
    return tickets[0]


class TestTicketLifecycle:
    def test_pending_to_new_creates_board_ticket(self, client, world):
        order_id = _create(client, world).json()["id"]
        res = _send_to_kitchen(client, world, order_id)
        assert res.status_code == 200, res.text

        ticket = _first_ticket(client, world)
        assert ticket["order_id"] == order_id
        assert ticket["status"] == "NEW"
        assert ticket["order_number"] == 1
        assert ticket["table_name"] == "T1"
        assert ticket["items"][0]["product_name_snapshot"] == "Plov"

        # Board pushes only NEW before the kitchen moves things along.
        tickets = _tickets(client, world).json()
        assert all(t["status"] == "NEW" for t in tickets)

    def test_board_ticket_mirrors_order_kitchen_status(self, client, world):
        order_id = _create(client, world).json()["id"]
        _send_to_kitchen(client, world, order_id)
        ticket_id = _first_ticket(client, world)["id"]

        for step in ("PREPARING", "READY"):
            res = client.patch(
                f"{TICKETS_URL}/{ticket_id}/status",
                headers=owner_headers(world),
                json={"status": step},
            )
            assert res.status_code == 200, res.text
            assert res.json()["status"] == step

            # Single source of truth stays the order (Section 34).
            order = client.get(
                f"/api/v1/orders/{order_id}", headers=owner_headers(world)
            ).json()
            assert order["kitchen_status"] == step

    def test_advance_rejects_backward_move(self, client, world):
        order_id = _create(client, world).json()["id"]
        _send_to_kitchen(client, world, order_id)
        ticket_id = _first_ticket(client, world)["id"]
        client.patch(
            f"{TICKETS_URL}/{ticket_id}/status",
            headers=owner_headers(world),
            json={"status": "PREPARING"},
        )
        res = client.patch(
            f"{TICKETS_URL}/{ticket_id}/status",
            headers=owner_headers(world),
            json={"status": "NEW"},
        )
        assert res.status_code == 422

    def test_unknown_ticket_status_rejected_by_schema(self, client, world):
        order_id = _create(client, world).json()["id"]
        _send_to_kitchen(client, world, order_id)
        ticket_id = _first_ticket(client, world)["id"]
        res = client.patch(
            f"{TICKETS_URL}/{ticket_id}/status",
            headers=owner_headers(world),
            json={"status": "NOPE"},
        )
        assert res.status_code == 422

    def test_terminal_order_removes_ticket(self, client, world):
        order_id = _create(client, world).json()["id"]
        _send_to_kitchen(client, world, order_id)
        _first_ticket(client, world)  # ticket exists on the board

        # DRAFT -> OPEN -> COMPLETED (order status machine).
        client.patch(
            f"/api/v1/orders/{order_id}/status",
            headers=owner_headers(world),
            json={"status": "OPEN"},
        )
        done = client.patch(
            f"/api/v1/orders/{order_id}/status",
            headers=owner_headers(world),
            json={"status": "COMPLETED"},
        )
        assert done.status_code == 200
        assert _tickets(client, world).json() == []


class TestTicketPermissionsAndTenancy:
    def test_kitchen_role_can_view_and_advance(self, client, world):
        order_id = _create(client, world).json()["id"]
        _send_to_kitchen(client, world, order_id, headers=kitchen_headers(world))

        res = _tickets(client, world, headers=kitchen_headers(world))
        assert res.status_code == 200
        ticket_id = res.json()[0]["id"]

        adv = client.patch(
            f"{TICKETS_URL}/{ticket_id}/status",
            headers=kitchen_headers(world),
            json={"status": "PREPARING"},
        )
        assert adv.status_code == 200

    def test_accountant_cannot_view_tickets(self, client, world):
        accountant = auth_headers(
            world.owner_a.id, world.restaurant_a.id, ROLE_TEMPLATES["ACCOUNTANT"]
        )
        res = _tickets(client, world, headers=accountant)
        assert res.status_code == 403

    def test_cross_tenant_ticket_request_is_empty_or_404(self, client, world):
        b_owner = auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))
        b_order = client.post(
            "/api/v1/orders",
            headers=b_owner,
            json={
                "branch_id": str(world.branch_b.id),
                "source": "POS",
                "items": [{"product_id": str(world.product_b.id), "quantity": 1, "modifiers": []}],
            },
        ).json()["id"]
        client.patch(
            f"/api/v1/orders/{b_order}/kitchen-status",
            headers=b_owner,
            json={"kitchen_status": "NEW"},
        )

        # A's board does not list B's tickets...
        b_ticket = client.get(
            f"{TICKETS_URL}?branch_id={world.branch_b.id}", headers=b_owner
        ).json()[0]
        assert _tickets(client, world).json() == []
        assert _tickets(client, world, branch_id=world.branch_b.id).json() == []

        # ...and A cannot advance B's ticket (404, presence never disclosed).
        res = client.patch(
            f"{TICKETS_URL}/{b_ticket['id']}/status",
            headers=owner_headers(world),
            json={"status": "PREPARING"},
        )
        assert res.status_code == 404


class TestKitchenStations:
    def test_create_and_list_station(self, client, world):
        res = client.post(
            "/api/v1/kitchen/stations",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id), "name": "Grill"},
        )
        assert res.status_code == 201, res.text
        assert res.json()["name"] == "Grill"

        listed = client.get("/api/v1/kitchen/stations", headers=owner_headers(world)).json()
        assert any(s["name"] == "Grill" for s in listed)

        scoped = client.get(
            f"/api/v1/kitchen/stations?branch_id={world.branch_b.id}",
            headers=owner_headers(world),
        ).json()
        assert scoped == []

    def test_create_station_requires_manage_permission(self, client, world):
        res = client.post(
            "/api/v1/kitchen/stations",
            headers=waiter_headers(world),
            json={"branch_id": str(world.branch_a.id), "name": "Grill"},
        )
        assert res.status_code == 403


def _recv(ws):
    """Next kitchen event; the generic `order_changed` hint the dashboards use for
    live refresh rides the same socket and is not what these tests are about."""
    while True:
        msg = ws.receive_json()
        if msg.get("event") != "order_changed":
            return msg


class TestKitchenWebSocket:
    def _ws_url(self, world, token, branch=None):
        url = f"/api/v1/ws/kitchen?token={token}"
        if branch is not None:
            url += f"&branch_id={branch}"
        return url

    def test_event_delivered_to_own_tenant(self, client, world):
        token = create_access_token(
            subject=str(world.kitchen_a.id),
            restaurant_id=str(world.restaurant_a.id),
            permission_codes=ROLE_TEMPLATES["KITCHEN"],
        )
        with client.websocket_connect(self._ws_url(world, token, world.branch_a.id)) as ws:
            order_id = _create(client, world).json()["id"]

            res = _send_to_kitchen(client, world, order_id, headers=owner_headers(world))
            assert res.status_code == 200, res.text
            msg = _recv(ws)
            assert msg["event"] == "order_sent_to_kitchen"
            assert msg["ticket"]["order_id"] == order_id
            assert msg["ticket"]["status"] == "NEW"

            client.patch(
                f"/api/v1/orders/{order_id}/kitchen-status",
                headers=owner_headers(world),
                json={"kitchen_status": "PREPARING"},
            )
            msg = _recv(ws)
            assert msg["event"] == "order_preparing"
            assert msg["ticket"]["status"] == "PREPARING"

            client.patch(
                f"/api/v1/orders/{order_id}/kitchen-status",
                headers=owner_headers(world),
                json={"kitchen_status": "READY"},
            )
            msg = _recv(ws)
            assert msg["event"] == "order_ready"

    def test_advance_via_ticket_endpoint_broadcasts(self, client, world):
        token = create_access_token(
            subject=str(world.owner_a.id),
            restaurant_id=str(world.restaurant_a.id),
            permission_codes=list(ALL_PERMISSIONS),
        )
        with client.websocket_connect(self._ws_url(world, token, world.branch_a.id)) as ws:
            order_id = _create(client, world).json()["id"]
            _send_to_kitchen(client, world, order_id)
            assert _recv(ws)["event"] == "order_sent_to_kitchen"

            ticket_id = _first_ticket(client, world)["id"]
            client.patch(
                f"{TICKETS_URL}/{ticket_id}/status",
                headers=owner_headers(world),
                json={"status": "PREPARING"},
            )
            msg = _recv(ws)
            assert msg["event"] == "order_preparing"
            assert msg["ticket"]["id"] == ticket_id

    def test_invalid_token_is_rejected(self, client, world):
        url = "/api/v1/ws/kitchen?token=not-a-real-token"
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(url):
                pass

    def test_expired_token_is_rejected(self, client, world):
        from datetime import datetime, timedelta, timezone

        expired = create_access_token(
            subject=str(world.kitchen_a.id),
            restaurant_id=str(world.restaurant_a.id),
            permission_codes=ROLE_TEMPLATES["KITCHEN"],
            expires_delta=timedelta(minutes=-1),
        )
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(self._ws_url(world, expired, None)):
                pass

    def test_foreign_branch_is_rejected(self, client, world):
        token = create_access_token(
            subject=str(world.kitchen_a.id),
            restaurant_id=str(world.restaurant_a.id),
            permission_codes=ROLE_TEMPLATES["KITCHEN"],
        )
        # B's branch with A's token -> close (4404).
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                self._ws_url(world, token, world.branch_b.id)
            ):
                pass


async def test_manager_never_crosses_tenants():
    """Unit-level isolation proof: a fake socket in restaurant B's registry
    never receives an event broadcast to restaurant A."""
    from app.websocket import manager as manager_module

    class FakeWs:
        def __init__(self):
            self.sent: list[str] = []

        async def send_text(self, payload: str) -> None:
            self.sent.append(payload)

    fake_b = FakeWs()
    fake_a = FakeWs()

    rid_a, rid_b = uuid.uuid4(), uuid.uuid4()
    branch_a, branch_b = uuid.uuid4(), uuid.uuid4()

    m = manager_module.ConnectionManager()
    await m.connect(rid_a, branch_a, fake_a)
    await m.connect(rid_b, branch_b, fake_b)

    await m.broadcast(rid_a, branch_a, {"event": "order_ready"})
    assert fake_a.sent == ['{"event": "order_ready"}']

    # B must be untouched by A's traffic; and A untouched by B's.
    await m.broadcast(rid_b, branch_b, {"event": "order_ready", "who": "b"})
    assert len(fake_a.sent) == 1
    assert fake_b.sent == ['{"event": "order_ready", "who": "b"}']