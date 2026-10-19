"""Long-polling receiver: the same bot behaviour as the webhook, fed by
`getUpdates` (for a backend with no public HTTPS address)."""

from __future__ import annotations

import app.integrations.telegram as telegram_api
import app.services.telegram_poller as poller
from tests.conftest import owner_headers
from tests.test_telegram import _patch_telegram_client


def _connect(client, world, monkeypatch):
    _patch_telegram_client(monkeypatch)
    res = client.post("/api/v1/restaurant/telegram", headers=owner_headers(world), json={"bot_token": "good-token"})
    assert res.status_code == 200, res.text


class TestPollOnce:
    async def test_polled_updates_drive_the_bot_and_advance_the_offset(self, client, world, db, monkeypatch):
        _connect(client, world, monkeypatch)
        sent: list[str] = []

        async def fake_send(token, chat_id, text, reply_markup=None, parse_mode=None):
            sent.append(text)
            return {}

        monkeypatch.setattr(telegram_api, "send_message", fake_send)

        chat = {"id": 777001}
        batch = [
            {"update_id": 40, "message": {"chat": chat, "text": "/start", "from": {"id": 777001}}},
            {"update_id": 41, "callback_query": {"id": "a", "message": {"chat": chat}, "data": f"cat:{world.category_a.id}"}},
        ]
        calls: list[int] = []

        async def fake_get_updates(token, offset, timeout):
            calls.append(offset)
            return batch if offset == 0 else []

        monkeypatch.setattr(telegram_api, "get_updates", fake_get_updates)

        offset = await poller.poll_once(world.restaurant_a.id, "good-token", 0)
        assert offset == 42 and calls == [0]
        assert sent, "the bot replied to /start"

        # Next poll continues from the returned offset and finds nothing new.
        assert await poller.poll_once(world.restaurant_a.id, "good-token", offset) == 42

    async def test_stops_handling_when_token_was_rotated(self, client, world, db, monkeypatch):
        _connect(client, world, monkeypatch)
        handled: list[dict] = []

        async def fake_handle(session, restaurant, update):
            handled.append(update)

        monkeypatch.setattr(poller.telegram_bot_service, "handle_update", fake_handle)

        async def fake_get_updates(token, offset, timeout):
            return [{"update_id": 1, "message": {"chat": {"id": 1}, "text": "/start"}}]

        monkeypatch.setattr(telegram_api, "get_updates", fake_get_updates)
        # Poller started with an old token that no longer matches the restaurant.
        await poller.poll_once(world.restaurant_a.id, "old-token", 0)
        assert handled == []


class TestReconcile:
    async def test_starts_one_task_per_connected_bot_and_stops_on_disconnect(self, client, world, monkeypatch):
        _connect(client, world, monkeypatch)

        async def idle(token, offset, timeout):
            import asyncio

            await asyncio.sleep(3600)

        monkeypatch.setattr(telegram_api, "get_updates", idle)
        try:
            await poller.reconcile()
            assert list(poller._tasks) == [world.restaurant_a.id]

            client.delete("/api/v1/restaurant/telegram", headers=owner_headers(world))
            await poller.reconcile()
            assert poller._tasks == {}
        finally:
            await poller.stop_all()
