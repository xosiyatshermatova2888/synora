"""Telegram ordering bot — one bot per restaurant. `app.integrations.telegram`
(the actual Telegram Bot HTTP API calls) is monkeypatched throughout; these
tests exercise `connect_bot`/`disconnect_bot`, the webhook's auth boundary,
and the full conversation state machine end to end.
"""

from __future__ import annotations

import uuid

import app.integrations.telegram as telegram_api
import app.services.telegram_bot as telegram_bot_service
from tests.conftest import owner_headers, waiter_headers

FIXED_WEBHOOK_SECRET = "test-webhook-secret-fixed"


async def _fake_get_me(token: str) -> dict:
    if token == "bad-token":
        raise telegram_api.TelegramError("Unauthorized", 401)
    return {"id": 111, "username": "test_restaurant_bot", "is_bot": True}


async def _noop(*args, **kwargs):
    return {}


def _patch_telegram_client(monkeypatch):
    monkeypatch.setattr(telegram_api, "get_me", _fake_get_me)
    monkeypatch.setattr(telegram_api, "set_webhook", _noop)
    monkeypatch.setattr(telegram_api, "delete_webhook", _noop)
    monkeypatch.setattr(telegram_api, "send_message", _noop)
    monkeypatch.setattr(telegram_api, "answer_callback_query", _noop)
    # Deterministic secret so tests don't need to read it back across a
    # different DB session than the one the API route committed with.
    monkeypatch.setattr(telegram_bot_service.secrets, "token_urlsafe", lambda n: FIXED_WEBHOOK_SECRET)


class TestConnectBot:
    def test_connects_with_valid_token(self, client, world, monkeypatch):
        _patch_telegram_client(monkeypatch)
        res = client.post(
            "/api/v1/restaurant/telegram",
            headers=owner_headers(world),
            json={"bot_token": "good-token"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["telegram_connected"] is True
        assert body["telegram_bot_username"] == "test_restaurant_bot"

    def test_rejects_invalid_token(self, client, world, monkeypatch):
        _patch_telegram_client(monkeypatch)
        res = client.post(
            "/api/v1/restaurant/telegram",
            headers=owner_headers(world),
            json={"bot_token": "bad-token"},
        )
        assert res.status_code == 422

    def test_waiter_cannot_connect_bot(self, client, world, monkeypatch):
        _patch_telegram_client(monkeypatch)
        res = client.post(
            "/api/v1/restaurant/telegram",
            headers=waiter_headers(world),
            json={"bot_token": "good-token"},
        )
        assert res.status_code == 403

    def test_disconnect_clears_connection(self, client, world, monkeypatch):
        _patch_telegram_client(monkeypatch)
        client.post("/api/v1/restaurant/telegram", headers=owner_headers(world), json={"bot_token": "good-token"})
        res = client.delete("/api/v1/restaurant/telegram", headers=owner_headers(world))
        assert res.status_code == 200, res.text
        assert res.json()["telegram_connected"] is False


def _connect(client, world, monkeypatch) -> str:
    _patch_telegram_client(monkeypatch)
    res = client.post("/api/v1/restaurant/telegram", headers=owner_headers(world), json={"bot_token": "good-token"})
    assert res.status_code == 200, res.text
    return FIXED_WEBHOOK_SECRET


class TestWebhookAuth:
    async def test_unknown_restaurant_404s(self, client):
        res = client.post(
            f"/api/v1/telegram/webhook/{uuid.uuid4()}",
            headers={"X-Telegram-Bot-Api-Secret-Token": "whatever"},
            json={"update_id": 1},
        )
        assert res.status_code == 404

    def test_wrong_secret_403s(self, client, world, monkeypatch):
        _connect(client, world, monkeypatch)
        res = client.post(
            f"/api/v1/telegram/webhook/{world.restaurant_a.id}",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            json={"update_id": 1},
        )
        assert res.status_code == 403

    def test_missing_secret_403s(self, client, world, monkeypatch):
        _connect(client, world, monkeypatch)
        res = client.post(f"/api/v1/telegram/webhook/{world.restaurant_a.id}", json={"update_id": 1})
        assert res.status_code == 403
