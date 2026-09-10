"""Payme (Paycom) Merchant API webhook tests (Phase M, Section 30 against the
published spec: JSON-RPC 2.0, HTTP 200 always, tiyin amounts, ms timestamps,
Basic-auth, idempotent replays, unique provider-txn key)."""

from __future__ import annotations

import base64
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.order import Order
from app.models.payment import Payment
from tests.conftest import owner_headers

ORDER_TOTAL = 45000  # UZS; product_a "Plov" = 45 000.00
TIYIN = ORDER_TOTAL * 100  # 4 500 000


def _basic(login: str = "Paycom", key: str = "TEST_KEY") -> dict[str, str]:
    token = base64.b64encode(f"{login}:{key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _rpc(method: str, params: dict, id=1) -> dict:
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params}


def _order_id(client, world, headers=None):
    headers = headers or owner_headers(world)
    created = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "branch_id": str(world.branch_a.id),
            "table_id": str(world.table_a.id),
            "source": "POS",
            "discount": "0.00",
            "items": [
                {"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}
            ],
        },
    )
    assert created.status_code == 201, created.text
    oid = created.json()["id"]
    opened = client.patch(
        f"/api/v1/orders/{oid}/status",
        headers=headers,
        json={"status": "OPEN"},
    )
    assert opened.status_code == 200, opened.text
    return oid


def _txn_params(order_id: str) -> dict:
    return {"id": "64be49a8c0f2a64e8a000001", "time": 1730000000000, "amount": TIYIN, "account": {"order_id": order_id}}


@pytest.fixture(autouse=True)
def _payme_credentials(monkeypatch):
    monkeypatch.setattr(settings, "payme_key", "TEST_KEY")
    monkeypatch.setattr(settings, "payme_login", "Paycom")


class TestCheckPerform:
    def test_open_order_allows_payment(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("CheckPerformTransaction", _txn_params(oid)),
        )
        assert res.status_code == 200
        assert res.json()["result"] == {"allow": True}

    def test_unknown_order_rejected_31050(self, client, world):
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("CheckPerformTransaction", _txn_params("00000000-0000-0000-0000-000000000000")),
        )
        assert res.json()["error"]["code"] == -31050

    def test_overpayment_rejected_31001(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("CheckPerformTransaction", {**_txn_params(oid), "amount": TIYIN + 100}),
        )
        assert res.json()["error"]["code"] == -31001

    def test_draft_order_not_payable(self, client, world):
        headers = owner_headers(world)
        created = client.post(
            "/api/v1/orders",
            headers=headers,
            json={
                "branch_id": str(world.branch_a.id),
                "source": "POS",
                "items": [{"product_id": str(world.product_a.id), "quantity": 1, "modifiers": []}],
            },
        )
        oid = created.json()["id"]  # stays DRAFT
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("CheckPerformTransaction", _txn_params(oid)),
        )
        assert res.json()["error"]["code"] in (-31001, -31008)


class TestAuth:
    def test_bad_credit_fails_32504(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers={"Authorization": "Basic " + base64.b64encode(b"Paycom:WRONG").decode()},
            json=_rpc("CheckPerformTransaction", _txn_params(oid)),
        )
        assert res.status_code == 200
        assert res.json()["error"]["code"] == -32504

    def test_missing_auth_fails_32504(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            json=_rpc("CheckPerformTransaction", _txn_params(oid)),
        )
        assert res.json()["error"]["code"] == -32504


class TestCreatePerform:
    async def test_happy_path_sets_state_and_completes_order(self, client, world, db):
        oid = _order_id(client, world)
        created = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("CreateTransaction", _txn_params(oid)),
        )
        assert created.status_code == 200
        body = created.json()["result"]
        assert body["state"] == 1
        assert body["transaction"]

        performed = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("PerformTransaction", _txn_params(oid)),
        )
        assert performed.json()["result"]["state"] == 2

        order = await db.scalar(select(Order).where(Order.id == UUID(oid)))
        assert order.status == "COMPLETED"
        payment = await db.scalar(select(Payment).where(Payment.order_id == UUID(oid)))
        assert payment.status == "PAID"
        assert payment.method == "PAYME"
        assert payment.provider == "PAYME"
        assert payment.provider_transaction_id == _txn_params(oid)["id"]

    def test_replayed_create_is_idempotent(self, client, world):
        oid = _order_id(client, world)
        params = _txn_params(oid)
        first = client.post("/api/v1/payments/webhooks/payme", headers=_basic(), json=_rpc("CreateTransaction", params))
        second = client.post("/api/v1/payments/webhooks/payme", headers=_basic(), json=_rpc("CreateTransaction", params))
        assert first.json()["result"]["transaction"] == second.json()["result"]["transaction"]
        # Only one Payment row.
        assert client.get(f"/api/v1/orders/{oid}/payments", headers=owner_headers(world)).json()
        payments = client.get(f"/api/v1/orders/{oid}/payments", headers=owner_headers(world)).json()
        assert len(payments) == 1

    def test_perform_unknown_txn_31003(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("PerformTransaction", _txn_params(oid)),
        )
        assert res.json()["error"]["code"] == -31003

    def test_cancel_after_perform_31007(self, client, world):
        oid = _order_id(client, world)
        client.post("/api/v1/payments/webhooks/payme", headers=_basic(), json=_rpc("CreateTransaction", _txn_params(oid)))
        client.post("/api/v1/payments/webhooks/payme", headers=_basic(), json=_rpc("PerformTransaction", _txn_params(oid)))
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("CancelTransaction", {**_txn_params(oid), "reason": 4}),
        )
        assert res.json()["error"]["code"] == -31007


class TestCancel:
    async def test_cancel_pending_marks_void_and_keeps_order_open(self, client, world, db):
        oid = _order_id(client, world)
        client.post("/api/v1/payments/webhooks/payme", headers=_basic(), json=_rpc("CreateTransaction", _txn_params(oid)))
        res = client.post(
            "/api/v1/payments/webhooks/payme",
            headers=_basic(),
            json=_rpc("CancelTransaction", {**_txn_params(oid), "reason": 4}),
        )
        assert res.json()["result"]["state"] == -1

        payment = await db.scalar(select(Payment).where(Payment.order_id == UUID(oid)))
        assert payment.status == "VOID"
        order = await db.scalar(select(Order).where(Order.id == UUID(oid)))
        assert order.status == "OPEN"


class TestCheckoutEndpoint:
    def test_checkout_link_requires_finance_manage(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            f"/api/v1/payments/{oid}/payme-checkout",
            headers=owner_headers(world),
            json={"amount": "45000.00"},
        )
        assert res.status_code == 200, res.text
        url = res.json()["checkout_url"]
        assert "account[order_id]" in url
        assert str(oid) in url

    def test_checkout_partial_payment_ok(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            f"/api/v1/payments/{oid}/payme-checkout",
            headers=owner_headers(world),
            json={"amount": "20000.00"},
        )
        assert res.status_code == 200

    def test_checkout_rejects_overpayment(self, client, world):
        oid = _order_id(client, world)
        res = client.post(
            f"/api/v1/payments/{oid}/payme-checkout",
            headers=owner_headers(world),
            json={"amount": "50000.00"},
        )
        assert res.status_code == 404