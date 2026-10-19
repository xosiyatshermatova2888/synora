"""Long-polling receiver for restaurant Telegram bots.

Telegram only delivers webhooks to a public HTTPS address, which a PC on a
local network (or a dev box) doesn't have. With `TELEGRAM_POLLING=true` the
backend instead asks Telegram for new updates (`getUpdates`) for every
connected restaurant bot and feeds them to the SAME `handle_update` the
webhook endpoint uses — so the bot behaves identically, it just needs this
backend to be running. Production with a real domain should keep webhooks.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import httpx
from sqlalchemy import select

from app.database.session import SessionLocal
from app.integrations import telegram as telegram_api
from app.models.restaurant import Restaurant
from app.services import telegram_bot as telegram_bot_service

logger = logging.getLogger("synora.telegram_poller")

POLL_TIMEOUT_SECONDS = 25
RECONCILE_EVERY_SECONDS = 10

# restaurant_id -> (token the task was started with, task)
_tasks: dict[uuid.UUID, tuple[str, asyncio.Task]] = {}


async def poll_once(restaurant_id: uuid.UUID, token: str, offset: int) -> int:
    """Fetch one batch of updates and handle them. Returns the next offset."""
    updates = await telegram_api.get_updates(token, offset, POLL_TIMEOUT_SECONDS)
    for update in updates:
        offset = max(offset, int(update["update_id"]) + 1)
        try:
            async with SessionLocal() as session:
                restaurant = await session.get(Restaurant, restaurant_id)
                if restaurant is None or restaurant.telegram_bot_token != token:
                    return offset  # disconnected / token rotated while polling
                await telegram_bot_service.handle_update(session, restaurant, update)
        except Exception:  # noqa: BLE001 — one bad update must not stop the bot
            logger.exception("telegram update %s failed", update.get("update_id"))
    return offset


async def _poll_loop(restaurant_id: uuid.UUID, token: str) -> None:
    offset = 0
    delay = 1.0
    webhook_cleared = False
    while True:
        try:
            offset = await poll_once(restaurant_id, token, offset)
            delay = 1.0
        except asyncio.CancelledError:
            raise
        except telegram_api.TelegramError as exc:
            if exc.error_code == 409 and not webhook_cleared:
                # A webhook is registered; polling mode means this backend owns
                # the bot, so remove it (getUpdates is refused while one is set).
                webhook_cleared = True
                try:
                    await telegram_api.delete_webhook(token)
                except Exception:  # noqa: BLE001
                    logger.exception("could not delete webhook for %s", restaurant_id)
                continue
            logger.warning("telegram polling error for %s: %s", restaurant_id, exc)
            await asyncio.sleep(delay)
            delay = min(30.0, delay * 2)
        except httpx.TransportError as exc:
            # DNS / TLS / timeout trouble on the restaurant's internet line: expected,
            # self-healing (we retry with backoff) — a one-line warning is enough.
            logger.warning("telegram unreachable for %s (%s: %s); retrying in %.0fs",
                           restaurant_id, type(exc).__name__, exc, delay)
            await asyncio.sleep(delay)
            delay = min(30.0, delay * 2)
        except Exception:  # noqa: BLE001 — anything else is a real bug: keep the traceback
            logger.exception("telegram polling crashed for %s", restaurant_id)
            await asyncio.sleep(delay)
            delay = min(30.0, delay * 2)


async def reconcile() -> None:
    """Start/stop one polling task per connected bot so connect/disconnect in
    Settings takes effect without restarting the backend."""
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Restaurant.id, Restaurant.telegram_bot_token).where(
                    Restaurant.telegram_bot_token.is_not(None),
                    Restaurant.telegram_webhook_secret.is_not(None),
                )
            )
        ).all()
    wanted = {rid: token for rid, token in rows if token}

    for rid in list(_tasks):
        token, task = _tasks[rid]
        if wanted.get(rid) != token:
            task.cancel()
            del _tasks[rid]
    for rid, token in wanted.items():
        if rid not in _tasks:
            _tasks[rid] = (token, asyncio.create_task(_poll_loop(rid, token)))
            logger.info("telegram polling started for restaurant %s", rid)


async def run_forever() -> None:
    while True:
        try:
            await reconcile()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("telegram poller reconcile failed")
        await asyncio.sleep(RECONCILE_EVERY_SECONDS)


async def stop_all() -> None:
    for _token, task in _tasks.values():
        task.cancel()
    _tasks.clear()
