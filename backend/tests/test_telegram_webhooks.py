"""Webhook mode: after a deploy / database restore every connected bot is
re-pointed at this server automatically."""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.models.restaurant import Restaurant
from app.services import telegram_bot
from app.integrations import telegram as telegram_api


async def test_registers_each_connected_bot_on_https(world, db, monkeypatch):
    world.restaurant_a.telegram_bot_token = "111:AAA"
    world.restaurant_a.telegram_webhook_secret = None  # e.g. restored from a polling-mode database
    await db.commit()

    calls = []

    async def fake_set_webhook(token, url, secret):
        calls.append((token, url, secret))

    monkeypatch.setattr(telegram_api, "set_webhook", fake_set_webhook)
    monkeypatch.setattr(settings, "public_app_url", "https://synora.example.uz")

    await telegram_bot.register_all_webhooks()

    assert len(calls) == 1  # restaurant B has no bot
    token, url, secret = calls[0]
    assert token == "111:AAA"
    assert url == f"https://synora.example.uz/api/v1/telegram/webhook/{world.restaurant_a.id}"
    assert secret

    await db.refresh(world.restaurant_a)
    stored = await db.scalar(select(Restaurant.telegram_webhook_secret).where(Restaurant.id == world.restaurant_a.id))
    assert stored == secret  # the receiver can now verify Telegram's header


async def test_does_nothing_without_a_public_https_url(world, db, monkeypatch):
    world.restaurant_a.telegram_bot_token = "111:AAA"
    await db.commit()
    calls = []

    async def fake_set_webhook(*args):
        calls.append(args)

    monkeypatch.setattr(telegram_api, "set_webhook", fake_set_webhook)
    for url in ("http://localhost:3000", "http://synora.example.uz", ""):
        monkeypatch.setattr(settings, "public_app_url", url)
        await telegram_bot.register_all_webhooks()
    assert calls == []


async def test_one_failing_bot_does_not_stop_the_others(world, db, monkeypatch):
    world.restaurant_a.telegram_bot_token = "111:AAA"
    world.restaurant_b.telegram_bot_token = "222:BBB"
    await db.commit()
    seen = []

    async def flaky(token, url, secret):
        seen.append(token)
        if token == "111:AAA":
            raise RuntimeError("telegram down")

    monkeypatch.setattr(telegram_api, "set_webhook", flaky)
    monkeypatch.setattr(settings, "public_app_url", "https://synora.example.uz")
    await telegram_bot.register_all_webhooks()
    assert sorted(seen) == ["111:AAA", "222:BBB"]
