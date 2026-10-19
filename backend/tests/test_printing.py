"""Network receipt printing: ESC/POS output, printer settings (tenant + role
gates + LAN-only addresses), automatic kitchen tickets for Telegram/QR/Waiter
orders, fail-soft behaviour when a printer is down, cashier pre-check/receipt,
and the waiter's "bring the bill" request."""

from __future__ import annotations

import pytest

from app.integrations import escpos
from tests.conftest import (
    auth_headers,
    cashier_headers,
    headers_for_restaurant_b_waiter,
    owner_headers,
    waiter_headers,
)

PRINTER_IP = "192.168.1.50"


@pytest.fixture
def sent(monkeypatch):
    """Capture what would go to the printer instead of opening a socket."""
    calls: list[tuple[str, int, bytes]] = []

    async def fake_send(host, port, data, **_):
        calls.append((host, port, data))

    monkeypatch.setattr(escpos, "send", fake_send)
    return calls


def _printer(client, world, role="KITCHEN", **extra):
    res = client.post(
        "/api/v1/printers",
        headers=owner_headers(world),
        json={
            "branch_id": str(world.branch_a.id),
            "role": role,
            "name": f"{role.title()} printer",
            "host": PRINTER_IP,
            **extra,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _order(client, world, source="WAITER", headers=None, table=None):
    res = client.post(
        "/api/v1/orders",
        headers=headers or owner_headers(world),
        json={
            "branch_id": str(world.branch_a.id),
            "table_id": str(table or world.table_a.id),
            "source": source,
            "notes": "Tezroq iltimos",
            "items": [{"product_id": str(world.product_a.id), "quantity": 2, "notes": "achchiq emas", "modifiers": []}],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _jobs(client, world):
    res = client.get("/api/v1/print-jobs", headers=owner_headers(world))
    assert res.status_code == 200, res.text
    return res.json()


class TestEscpos:
    def test_ascii_normalisation(self):
        assert escpos.to_printable_ascii("O‘zbek g‘isht") == "O'zbek g'isht"
        assert escpos.to_printable_ascii("Плов ўзбек") == "Plov o'zbek"
        assert escpos.to_printable_ascii("café \U0001F600").isascii()

    def test_document_starts_with_init_and_ends_with_cut(self):
        data = escpos.Escpos(58).text("hello").feed(1).cut().to_bytes()
        assert data.startswith(b"\x1b@")
        assert data.endswith(b"\x1dVB\x00")
        assert escpos.Escpos(58).width == 32 and escpos.Escpos(80).width == 48

    @pytest.mark.parametrize("host", ["192.168.1.5", "10.0.0.7", "172.16.4.2"])
    def test_private_addresses_accepted(self, host):
        assert escpos.validate_private_ipv4(host) == host

    @pytest.mark.parametrize("host", ["127.0.0.1", "8.8.8.8", "169.254.169.254", "0.0.0.0", "printer.local", "::1"])
    def test_non_lan_addresses_rejected(self, host):
        with pytest.raises(ValueError):
            escpos.validate_private_ipv4(host)


class TestPrinterSettings:
    def test_owner_can_create_and_list(self, client, world):
        _printer(client, world)
        res = client.get("/api/v1/printers", headers=owner_headers(world))
        assert res.status_code == 200
        assert [p["role"] for p in res.json()] == ["KITCHEN"]

    def test_second_printer_for_same_role_conflicts(self, client, world):
        _printer(client, world)
        res = client.post(
            "/api/v1/printers",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_a.id), "role": "KITCHEN", "name": "dup", "host": "192.168.1.51"},
        )
        assert res.status_code == 409

    def test_public_or_loopback_host_is_rejected(self, client, world):
        for host in ("127.0.0.1", "8.8.8.8", "printer.local"):
            res = client.post(
                "/api/v1/printers",
                headers=owner_headers(world),
                json={"branch_id": str(world.branch_a.id), "role": "KITCHEN", "name": "x", "host": host},
            )
            assert res.status_code == 422, host

    def test_waiter_and_cashier_cannot_manage(self, client, world):
        body = {"branch_id": str(world.branch_a.id), "role": "KITCHEN", "name": "x", "host": PRINTER_IP}
        assert client.post("/api/v1/printers", headers=waiter_headers(world), json=body).status_code == 403
        assert client.get("/api/v1/printers", headers=cashier_headers(world)).status_code == 403

    def test_capabilities_is_booleans_only_for_any_order_reader(self, client, world):
        _printer(client, world, "RECEIPT")
        res = client.get(
            f"/api/v1/printers/capabilities?branch_id={world.branch_a.id}", headers=waiter_headers(world)
        )
        assert res.status_code == 200
        assert res.json() == {"kitchen": False, "receipt": True}

    def test_other_tenant_cannot_touch_printer(self, client, world):
        printer = _printer(client, world)
        b = headers_for_restaurant_b_waiter(world)
        # waiter B lacks users.manage -> 403; use an owner-level B token for 404 proof
        owner_b = auth_headers(world.owner_b.id, world.restaurant_b.id, ["users.manage", "orders.read"])
        assert client.patch(f"/api/v1/printers/{printer['id']}", headers=owner_b, json={"name": "hijack"}).status_code == 404
        assert client.delete(f"/api/v1/printers/{printer['id']}", headers=owner_b).status_code == 404
        assert client.post(f"/api/v1/printers/{printer['id']}/test", headers=owner_b).status_code == 404
        assert client.get("/api/v1/printers", headers=owner_b).json() == []
        assert b  # waiter B headers exist (sanity)

    def test_cannot_create_printer_for_other_tenants_branch(self, client, world):
        res = client.post(
            "/api/v1/printers",
            headers=owner_headers(world),
            json={"branch_id": str(world.branch_b.id), "role": "KITCHEN", "name": "x", "host": PRINTER_IP},
        )
        assert res.status_code == 404

    def test_test_print_sends_bytes_and_records_job(self, client, world, sent):
        printer = _printer(client, world)
        res = client.post(f"/api/v1/printers/{printer['id']}/test", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "PRINTED" and res.json()["kind"] == "TEST"
        assert sent[0][0] == PRINTER_IP and sent[0][1] == 9100
        assert b"TEST PRINT" in sent[0][2]


class TestKitchenAutoPrint:
    def test_waiter_order_prints_only_table_and_dishes(self, client, world, sent):
        _printer(client, world)
        order = _order(client, world, "WAITER")
        assert len(sent) == 1
        data = sent[0][2]
        assert f"#{order['order_number']}".encode() in data
        assert b"TABLE T1" in data and b"2x Plov" in data and b"achchiq emas" in data
        assert b"NOTE: Tezroq iltimos" in data
        # No money, no staff names, no restaurant header on the kitchen slip.
        for forbidden in (b"WAITER", b"SOURCE", b"TOTAL", b"Subtotal", b"UZS", b"Alpha Grill"):
            assert forbidden not in data, forbidden
        jobs = _jobs(client, world)
        assert [(j["kind"], j["status"], j["order_id"]) for j in jobs] == [("KITCHEN_TICKET", "PRINTED", order["id"])]

    def test_telegram_table_less_order_without_customer_still_prints(self, client, world, sent):
        _printer(client, world)
        order = _order(client, world, "TELEGRAM")
        assert len(sent) == 1 and f"#{order['order_number']}".encode() in sent[0][2]

    def test_cashier_printer_gets_a_full_copy_only_when_enabled(self, client, world, sent):
        _printer(client, world)  # kitchen
        receipt = _printer(client, world, role="RECEIPT", host="192.168.1.51")
        _order(client, world, "WAITER")
        assert len(sent) == 1  # copy not enabled yet: kitchen slip only

        res = client.patch(f"/api/v1/printers/{receipt['id']}", headers=owner_headers(world), json={"auto_print_orders": True})
        assert res.status_code == 200 and res.json()["auto_print_orders"] is True
        sent.clear()
        order = _order(client, world, "WAITER")
        by_host = {host: data for host, _port, data in sent}
        assert set(by_host) == {"192.168.1.50", "192.168.1.51"}
        full = by_host["192.168.1.51"]
        assert b"BUYURTMA / ORDER" in full and b"TOTAL" in full and b"Subtotal" in full and b"Plov" in full
        assert b"TOTAL" not in by_host["192.168.1.50"]  # the kitchen still sees no money
        kinds = sorted(j["kind"] for j in _jobs(client, world) if j["order_id"] == order["id"])
        assert kinds == ["KITCHEN_TICKET", "ORDER_COPY"]

    def test_qr_order_prints(self, client, world, sent):
        _printer(client, world)
        res = client.post(
            "/api/v1/public/orders",
            json={
                "restaurant_slug": world.restaurant_a.slug,
                "branch_id": str(world.branch_a.id),
                "table_id": str(world.table_a.id),
                "customer_name": "Guest",
                "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            },
        )
        assert res.status_code == 201, res.text
        assert len(sent) == 1 and b"TABLE T1" in sent[0][2] and b"Plov" in sent[0][2]

    def test_pos_order_prints_only_when_sent_to_kitchen(self, client, world, sent):
        _printer(client, world)
        order = _order(client, world, "POS")
        assert sent == []
        res = client.patch(
            f"/api/v1/orders/{order['id']}/kitchen-status", headers=owner_headers(world), json={"kitchen_status": "NEW"}
        )
        assert res.status_code == 200, res.text
        assert len(sent) == 1

    def test_no_printer_configured_is_silent(self, client, world, sent):
        _order(client, world, "WAITER")
        assert sent == [] and _jobs(client, world) == []

    def test_inactive_printer_is_skipped(self, client, world, sent):
        printer = _printer(client, world)
        client.patch(f"/api/v1/printers/{printer['id']}", headers=owner_headers(world), json={"is_active": False})
        _order(client, world, "WAITER")
        assert sent == []

    def test_dead_printer_never_fails_the_order_and_can_be_retried(self, client, world, monkeypatch):
        _printer(client, world)

        async def dead(*_a, **_k):
            raise ConnectionRefusedError("printer offline")

        monkeypatch.setattr(escpos, "send", dead)
        order = _order(client, world, "WAITER")  # still 201 (asserted in helper)
        jobs = _jobs(client, world)
        assert jobs[0]["status"] == "FAILED" and "offline" in jobs[0]["error"]
        assert jobs[0]["attempts"] == 3

        delivered = []

        async def ok(host, port, data, **_):
            delivered.append(data)

        monkeypatch.setattr(escpos, "send", ok)
        res = client.post(f"/api/v1/print-jobs/{jobs[0]['id']}/retry", headers=owner_headers(world))
        assert res.status_code == 200 and res.json()["status"] == "PRINTED"
        assert len(delivered) == 1 and f"#{order['order_number']}".encode() in delivered[0]

    def test_print_jobs_are_tenant_scoped(self, client, world, sent):
        _printer(client, world)
        _order(client, world, "WAITER")
        owner_b = auth_headers(world.owner_b.id, world.restaurant_b.id, ["users.manage"])
        assert client.get("/api/v1/print-jobs", headers=owner_b).json() == []
        job_id = _jobs(client, world)[0]["id"]
        assert client.post(f"/api/v1/print-jobs/{job_id}/retry", headers=owner_b).status_code == 404

    def test_kitchen_reprint_endpoint(self, client, world, sent):
        _printer(client, world)
        order = _order(client, world, "WAITER")
        res = client.post(f"/api/v1/orders/{order['id']}/reprint-kitchen", headers=waiter_headers(world))
        assert res.status_code == 200 and res.json()["status"] == "PRINTED"
        assert len(sent) == 2


class TestWaiterOrderReachesCashier:
    def test_waiter_order_is_open_and_payable(self, client, world, sent):
        order = _order(client, world, "WAITER", headers=waiter_headers(world))
        assert order["status"] == "OPEN"
        res = client.post(
            "/api/v1/payments",
            headers=cashier_headers(world),
            json={"order_id": order["id"], "amount": order["total"], "method": "CASH"},
        )
        assert res.status_code == 201, res.text
        done = client.get(f"/api/v1/orders/{order['id']}", headers=owner_headers(world)).json()
        assert done["status"] == "COMPLETED"

    def test_pos_order_stays_draft_until_opened(self, client, world):
        assert _order(client, world, "POS")["status"] == "DRAFT"


class TestBills:
    def test_cashier_prints_precheck_then_receipt(self, client, world, sent):
        _printer(client, world, "RECEIPT")
        order = _order(client, world, "WAITER", headers=waiter_headers(world))
        pre = client.post(f"/api/v1/orders/{order['id']}/print?kind=PRECHECK", headers=cashier_headers(world))
        assert pre.status_code == 200 and pre.json()["status"] == "PRINTED"
        assert b"HISOB" in sent[-1][2] and b"TOTAL" in sent[-1][2] and b"Paid" not in sent[-1][2]

        client.post(
            "/api/v1/payments",
            headers=cashier_headers(world),
            json={"order_id": order["id"], "amount": order["total"], "method": "CASH"},
        )
        rec = client.post(f"/api/v1/orders/{order['id']}/print?kind=RECEIPT", headers=cashier_headers(world))
        assert rec.status_code == 200
        assert b"Naqd" in sent[-1][2] and b"Paid" in sent[-1][2] and b"HISOB" not in sent[-1][2]

    def test_print_without_receipt_printer_is_a_clear_error(self, client, world, sent):
        order = _order(client, world, "WAITER")
        res = client.post(f"/api/v1/orders/{order['id']}/print?kind=PRECHECK", headers=cashier_headers(world))
        assert res.status_code in (409, 422)
        assert "printer" in res.text.lower()

    def test_auto_print_receipt_on_full_payment(self, client, world, sent):
        _printer(client, world, "RECEIPT", auto_print_receipt=True)
        order = _order(client, world, "WAITER")
        sent.clear()
        client.post(
            "/api/v1/payments",
            headers=cashier_headers(world),
            json={"order_id": order["id"], "amount": order["total"], "method": "CARD"},
        )
        assert len(sent) == 1 and b"Karta" in sent[0][2]

    def test_no_auto_receipt_when_flag_off_or_partial(self, client, world, sent):
        _printer(client, world, "RECEIPT", auto_print_receipt=False)
        order = _order(client, world, "WAITER")
        client.post(
            "/api/v1/payments",
            headers=cashier_headers(world),
            json={"order_id": order["id"], "amount": order["total"], "method": "CASH"},
        )
        assert sent == []


class TestRequestBill:
    def test_waiter_request_stamps_order_and_notifies_cashier(self, client, world, sent):
        order = _order(client, world, "WAITER", headers=waiter_headers(world))
        res = client.post(f"/api/v1/orders/{order['id']}/request-bill", headers=waiter_headers(world))
        assert res.status_code == 200, res.text
        stamp = res.json()["bill_requested_at"]
        assert stamp is not None

        again = client.post(f"/api/v1/orders/{order['id']}/request-bill", headers=waiter_headers(world))
        # SQLite drops tzinfo on reload; compare the instant itself, not its suffix.
        assert again.json()["bill_requested_at"][:19] == stamp[:19]

        notes = client.get("/api/v1/notifications", headers=cashier_headers(world)).json()
        bill = [n for n in notes if n["type"] == "BILL_REQUEST"]
        assert len(bill) == 1
        assert "T1" in bill[0]["title"] and bill[0]["link"] == "/dashboard/payments"

    def test_draft_order_cannot_request_bill(self, client, world):
        order = _order(client, world, "POS")
        res = client.post(f"/api/v1/orders/{order['id']}/request-bill", headers=waiter_headers(world))
        assert res.status_code in (409, 422)

    def test_other_tenant_gets_404(self, client, world):
        order = _order(client, world, "WAITER")
        res = client.post(
            f"/api/v1/orders/{order['id']}/request-bill", headers=headers_for_restaurant_b_waiter(world)
        )
        assert res.status_code == 404


class TestDeliveryOnTicket:
    def test_telegram_delivery_order_prints_customer_and_address(self, client, world, sent):
        _printer(client, world)
        res = client.post(
            "/api/v1/orders",
            headers=owner_headers(world),
            json={
                "branch_id": str(world.branch_a.id),
                "source": "TELEGRAM",
                "delivery_type": "DELIVERY",
                "customer_name": "Aziz Karimov",
                "customer_phone": "+998901234567",
                "delivery_address": "Navoiy, Xalqlar do‘stligi ko‘chasi 12",
                "delivery_note": "2-qavat",
                "delivery_lat": "40.103000",
                "delivery_lng": "65.378000",
                "payment_method": "CARD_TRANSFER",
                "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            },
        )
        assert res.status_code == 201, res.text
        data = sent[0][2]
        assert b"DELIVERY" in data and b"Name: Aziz Karimov" in data
        assert b"Phone: +998901234567" in data
        assert b"Address: Navoiy, Xalqlar do'stligi ko'chasi 12" in data  # apostrophes normalised for the printer
        assert b"Note: 2-qavat" in data and b"GPS: 40.103000, 65.378000" in data
        # The slip that rides with the courier is complete: prices, total and what to collect.
        assert b"Plov" in data and b"1 x 45 000 UZS" in data
        assert b"TOTAL" in data and b"Subtotal" in data
        assert b"TO COLLECT" in data  # nothing paid yet
        assert b"Pay: card transfer" in data
        assert b"TABLE:" not in data  # no table on a delivery order

    def test_pickup_has_no_address_line(self, client, world, sent):
        _printer(client, world)
        client.post(
            "/api/v1/orders",
            headers=owner_headers(world),
            json={
                "branch_id": str(world.branch_a.id), "source": "TELEGRAM", "delivery_type": "PICKUP",
                "customer_name": "Aziz", "customer_phone": "+998901234567", "payment_method": "CASH",
                "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            },
        )
        assert b"PICKUP" in sent[0][2] and b"Address:" not in sent[0][2]


class TestLiveDashboard:
    def test_every_new_order_is_announced_to_open_dashboards(self, client, world):
        from app.core.permissions import ALL_PERMISSIONS
        from app.core.security import create_access_token

        token = create_access_token(
            subject=str(world.owner_a.id), restaurant_id=str(world.restaurant_a.id), permission_codes=list(ALL_PERMISSIONS)
        )
        with client.websocket_connect(f"/api/v1/ws/notifications?token={token}") as ws:
            order = _order(client, world, "WAITER")
            seen = [ws.receive_json() for _ in range(2)]
        events = {m["event"] for m in seen}
        assert "order_changed" in events
        changed = next(m for m in seen if m["event"] == "order_changed")
        assert changed["order_id"] == order["id"]
