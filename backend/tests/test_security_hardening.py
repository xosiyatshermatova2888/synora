"""Regression tests for the security-hardening pass: kiosk PIN login scope,
registration rate limit, upload content checks, log redaction and WebSocket
account checks."""

from __future__ import annotations

import struct
import zlib

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.core.logging import redact_secrets
from app.core.security import create_access_token
from app.utils import rate_limit
from tests.conftest import owner_headers


def _png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


# --- kiosk PIN login ----------------------------------------------------------


@pytest.fixture
def kiosk(client, world, monkeypatch):
    monkeypatch.setattr(settings, "waiter_restaurant_slug", world.restaurant_a.slug)
    h = owner_headers(world)

    def set_pin(user, pin):
        res = client.patch(f"/api/v1/users/{user.id}/pin", headers=h, json={"pin": pin})
        assert res.status_code == 200, res.text

    def login(user, pin):
        return client.post(
            "/api/v1/auth/pin-login",
            json={"branch_id": str(world.branch_a.id), "user_id": str(user.id), "pin": pin},
        )

    return set_pin, login


class TestKioskPin:
    def test_waiter_can_use_a_pin(self, world, kiosk):
        set_pin, login = kiosk
        set_pin(world.waiter_a, "4821")
        res = login(world.waiter_a, "4821")
        assert res.status_code == 200 and res.json()["access_token"]

    def test_owner_cannot_be_opened_with_a_pin(self, world, kiosk):
        set_pin, login = kiosk
        set_pin(world.owner_a, "1234")
        res = login(world.owner_a, "1234")
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid name or PIN."  # same message: no oracle for "right PIN, wrong role"

    def test_wrong_pin_locks_the_account_out_for_a_while(self, world, kiosk, monkeypatch):
        monkeypatch.setattr(rate_limit.login_limiter, "max_attempts", 5)  # production value (tests raise it)
        set_pin, login = kiosk
        set_pin(world.waiter_a, "4821")
        codes = [login(world.waiter_a, "0000").status_code for _ in range(5)]
        assert set(codes) == {401}
        assert login(world.waiter_a, "0000").status_code == 429
        assert login(world.waiter_a, "4821").status_code == 429  # even the right PIN, while locked

    def test_kiosk_is_closed_when_not_scoped_to_the_restaurant(self, client, world, monkeypatch):
        monkeypatch.setattr(settings, "waiter_restaurant_slug", "")
        assert client.get("/api/v1/auth/waiter-branches").json() == []


# --- registration -------------------------------------------------------------


class TestRegistrationLimit:
    def test_signups_per_address_are_capped(self, client, monkeypatch):
        monkeypatch.setattr(rate_limit._register_limiter, "max_attempts", 2)

        def register(n):
            return client.post(
                "/api/v1/auth/register",
                json={"restaurant_name": f"Spam {n}", "username": f"spam_{n}", "password": "TestPass123!", "full_name": "Spam Owner"},
            )

        assert register(1).status_code == 201
        assert register(2).status_code == 201
        res = register(3)
        assert res.status_code == 429


# --- uploads ------------------------------------------------------------------


class TestUploads:
    def _upload(self, client, world, data, content_type="image/png", name="x.png"):
        return client.post(
            "/api/v1/uploads/image", headers=owner_headers(world), files={"file": (name, data, content_type)}
        )

    def test_real_image_is_accepted(self, client, world, monkeypatch):
        from app.api.v1 import uploads

        async def fake_save(data, filename):
            return f"/uploads/test/{filename}"

        monkeypatch.setattr(uploads, "storage_save", fake_save)
        assert self._upload(client, world, _png()).status_code == 200

    def test_html_labelled_as_png_is_rejected(self, client, world):
        res = self._upload(client, world, b"<html><script>alert(1)</script></html>")
        assert res.status_code == 400

    def test_svg_and_executables_are_rejected(self, client, world):
        assert self._upload(client, world, b"<svg onload=alert(1)/>", "image/svg+xml", "x.svg").status_code == 400
        assert self._upload(client, world, b"MZ\x90\x00", "image/png", "x.png").status_code == 400


# --- log redaction ------------------------------------------------------------


class TestRedaction:
    def test_tokens_in_urls_are_masked(self):
        line = 'WebSocket /api/v1/ws/notifications?token=eyJhbGciOi.abc.def&branch_id=1 [accepted]'
        out = redact_secrets(line)
        assert "eyJhbGciOi" not in out and "token=***" in out and "branch_id=1" in out

    def test_plain_text_is_untouched(self):
        assert redact_secrets("order 12 paid") == "order 12 paid"


# --- WebSocket ----------------------------------------------------------------


class TestWebSocketAccount:
    async def test_deactivated_user_cannot_open_a_live_feed(self, client, world, db):
        token = create_access_token(
            subject=str(world.waiter_a.id), restaurant_id=str(world.restaurant_a.id), permission_codes=["orders.read"]
        )
        with client.websocket_connect(f"/api/v1/ws/notifications?token={token}") as ws:
            assert ws is not None  # active user: accepted

        world.waiter_a.is_active = False
        await db.commit()
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/v1/ws/notifications?token={token}"):
                pass


# --- ids in request bodies must belong to the caller's tenant ------------------


def _b_headers(world):
    from app.core.permissions import ALL_PERMISSIONS
    from tests.conftest import auth_headers

    return auth_headers(world.owner_b.id, world.restaurant_b.id, list(ALL_PERMISSIONS))


class TestCrossTenantReferences:
    """Tenant B sends tenant A's branch/category ids: every one must be a 404."""

    def test_branch_ids_of_another_tenant_are_refused(self, client, world):
        hb, a_branch = _b_headers(world), str(world.branch_a.id)
        attempts = {
            "table": ("POST", "/api/v1/tables", {"branch_id": a_branch, "name": "evil", "capacity": 2}),
            "inventory item": ("POST", "/api/v1/inventory-items", {"branch_id": a_branch, "name": "evil", "unit": "kg"}),
            "cash shift": ("POST", "/api/v1/cash-shifts/open", {"branch_id": a_branch, "opening_balance": "0"}),
            "printer": ("POST", "/api/v1/printers", {"branch_id": a_branch, "role": "KITCHEN", "name": "e", "host": "192.168.1.9"}),
            "order": ("POST", "/api/v1/orders", {"branch_id": a_branch, "table_id": str(world.table_b.id), "source": "WAITER",
                                                 "items": [{"product_id": str(world.product_b.id), "quantity": 1, "modifiers": []}]}),
        }
        for name, (method, path, body) in attempts.items():
            res = client.request(method, path, headers=hb, json=body)
            assert res.status_code in (404, 422), (name, res.status_code, res.text[:120])

    def test_category_of_another_tenant_cannot_be_used(self, client, world):
        hb = _b_headers(world)
        res = client.post("/api/v1/menu/products", headers=hb,
                          json={"category_id": str(world.category_a.id), "name": "evil", "price": "1.00"})
        assert res.status_code == 404
        res = client.patch(f"/api/v1/menu/products/{world.product_b.id}", headers=hb,
                           json={"category_id": str(world.category_a.id)})
        assert res.status_code == 404
        # ...and the product was not moved
        res = client.get(f"/api/v1/menu/products/{world.product_b.id}", headers=hb)
        assert res.json()["category_id"] == str(world.category_b.id)

    def test_a_table_from_another_branch_cannot_be_used(self, client, world):
        # table_a belongs to branch_a; ordering it "in" another branch id is refused
        res = client.post("/api/v1/orders", headers=owner_headers(world), json={
            "branch_id": str(uuid_other()), "table_id": str(world.table_a.id), "source": "WAITER",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1,
                       "modifiers": [{"modifier_id": str(world.large_mod.id), "quantity": 1}]}]})
        assert res.status_code == 404

    def test_own_branch_still_works(self, client, world):
        res = client.post("/api/v1/tables", headers=owner_headers(world),
                          json={"branch_id": str(world.branch_a.id), "name": "T9", "capacity": 2})
        assert res.status_code == 201


def uuid_other():
    import uuid

    return uuid.uuid4()


# --- uploads: stored extension follows the bytes -------------------------------


class TestUploadNaming:
    def test_double_extension_cannot_smuggle_html(self, client, world, monkeypatch):
        from app.api.v1 import uploads

        saved = {}

        async def fake_save(data, filename):
            saved["name"] = filename
            return f"/uploads/test/{filename}"

        monkeypatch.setattr(uploads, "storage_save", fake_save)
        res = client.post("/api/v1/uploads/image", headers=owner_headers(world),
                          files={"file": ("a.png.html", _png(), "image/png")})
        assert res.status_code == 200
        assert saved["name"].endswith(".png") and "html" not in saved["name"]


# --- per-address login lock must be far looser than per-account -----------------


class TestLoginLockScope:
    def test_five_typos_by_strangers_do_not_lock_the_address(self, client, world, monkeypatch):
        monkeypatch.setattr(rate_limit.login_limiter, "max_attempts", 5)
        monkeypatch.setattr(rate_limit.login_limiter, "ip_max_attempts", 30)
        for i in range(5):  # five different accounts, one failure each
            client.post("/api/v1/auth/login", json={"username": f"ghost{i}@x.io", "password": "wrong-password"})
        res = client.post("/api/v1/auth/login", json={"username": world.owner_a.username, "password": "TestPass123!"})
        assert res.status_code == 200  # the restaurant can still log in

    def test_one_account_is_still_locked_after_five_failures(self, client, world, monkeypatch):
        monkeypatch.setattr(rate_limit.login_limiter, "max_attempts", 5)
        monkeypatch.setattr(rate_limit.login_limiter, "ip_max_attempts", 30)
        codes = [client.post("/api/v1/auth/login", json={"username": world.owner_a.username, "password": "nope-nope"}).status_code
                 for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429


class TestClientAddress:
    def test_a_client_cannot_pick_its_own_rate_limit_bucket(self, client, monkeypatch):
        monkeypatch.setattr(rate_limit.login_limiter, "max_attempts", 100)
        monkeypatch.setattr(rate_limit.login_limiter, "ip_max_attempts", 3)
        codes = []
        for i in range(5):  # rotating the claimed (first) address changes nothing
            codes.append(client.post(
                "/api/v1/auth/login",
                json={"username": f"rot{i}@x.io", "password": "wrong-password"},
                headers={"X-Forwarded-For": f"10.9.8.{i}, 203.0.113.7"},
            ).status_code)
        assert codes[:3] == [401] * 3 and codes[3:] == [429, 429]


# --- money-moving actions need money permissions --------------------------------


class TestMoneyPermissions:
    def _open_order(self, client, world):
        res = client.post("/api/v1/orders", headers=owner_headers(world), json={
            "branch_id": str(world.branch_a.id), "table_id": str(world.table_a.id), "source": "WAITER",
            "items": [{"product_id": str(world.product_a.id), "quantity": 1,
                       "modifiers": [{"modifier_id": str(world.large_mod.id), "quantity": 1}]}]})
        assert res.status_code == 201, res.text
        return res.json()

    def test_waiter_and_kitchen_cannot_record_payments(self, client, world):
        from tests.conftest import kitchen_headers, waiter_headers

        order = self._open_order(client, world)
        for headers in (waiter_headers(world), kitchen_headers(world)):
            res = client.post("/api/v1/payments", headers=headers,
                              json={"order_id": order["id"], "method": "CASH", "amount": order["total"]})
            assert res.status_code == 403

    def test_waiter_and_kitchen_cannot_cancel_complete_or_refund(self, client, world):
        from tests.conftest import kitchen_headers, waiter_headers

        order = self._open_order(client, world)
        for headers in (waiter_headers(world), kitchen_headers(world)):
            for status in ("CANCELLED", "COMPLETED", "REFUNDED", "PARTIALLY_PAID"):
                res = client.patch(f"/api/v1/orders/{order['id']}/status", headers=headers, json={"status": status})
                assert res.status_code == 403, (status, res.status_code)
        still = client.get(f"/api/v1/orders/{order['id']}", headers=owner_headers(world)).json()
        assert still["status"] == "OPEN"

    def test_cashier_can_still_take_payment_and_cancel(self, client, world):
        from tests.conftest import cashier_headers

        order = self._open_order(client, world)
        h = cashier_headers(world)
        shift = client.post("/api/v1/cash-shifts/open", headers=h, json={"branch_id": str(world.branch_a.id), "opening_balance": "0"})
        # opening a shift is a finance.manage action; the owner opens it, the cashier takes the payment
        if shift.status_code == 403:
            client.post("/api/v1/cash-shifts/open", headers=owner_headers(world),
                        json={"branch_id": str(world.branch_a.id), "opening_balance": "0"})
        res = client.post("/api/v1/payments", headers=h, json={"order_id": order["id"], "method": "CASH", "amount": order["total"]})
        assert res.status_code == 201, res.text
        order2 = self._open_order(client, world)
        res = client.patch(f"/api/v1/orders/{order2['id']}/status", headers=h, json={"status": "CANCELLED"})
        assert res.status_code == 200

    def test_only_finance_managers_can_refund(self, client, world):
        from tests.conftest import cashier_headers

        order = self._open_order(client, world)
        client.post("/api/v1/cash-shifts/open", headers=owner_headers(world),
                    json={"branch_id": str(world.branch_a.id), "opening_balance": "0"})
        client.post("/api/v1/payments", headers=owner_headers(world),
                    json={"order_id": order["id"], "method": "CASH", "amount": order["total"]})
        res = client.patch(f"/api/v1/orders/{order['id']}/status", headers=cashier_headers(world), json={"status": "REFUNDED"})
        assert res.status_code == 403
        res = client.patch(f"/api/v1/orders/{order['id']}/status", headers=owner_headers(world), json={"status": "REFUNDED"})
        assert res.status_code == 200


# --- login timing ---------------------------------------------------------------


class TestLoginTiming:
    def test_unknown_and_known_users_cost_the_same(self, client, world):
        import time

        def avg(username, n=4):
            ts = []
            for _ in range(n):
                t0 = time.perf_counter()
                client.post("/api/v1/auth/login", json={"username": username, "password": "wrong-password-1"})
                ts.append(time.perf_counter() - t0)
            return sum(ts) / n

        avg(world.owner_a.username, 1)  # warm the hasher
        known, unknown = avg(world.owner_a.username), avg("nobody-here@x.io")
        assert unknown > known * 0.5, (known, unknown)  # unknown users must not answer ~10x faster
