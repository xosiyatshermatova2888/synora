"""Tell a Telegram customer when their order changes state.

Only orders placed through the Telegram bot have a chat to message. Messages
are sent as fire-and-forget side effects after the staff action committed, so
a Telegram outage or a customer who blocked the bot can never fail or slow
down the kitchen. Nothing about other customers is ever included.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.config import settings
from app.database.session import SessionLocal
from app.integrations import telegram as telegram_api
from app.models.customer import Customer
from app.models.restaurant import Restaurant

logger = logging.getLogger("synora.customer_notify")

_tasks: set[asyncio.Task] = set()


def _text(event: str, number: int, delivery_type: str | None, restaurant_phone: str | None) -> str | None:
    pickup = delivery_type == "PICKUP"
    if event == "PREPARING":
        return f"👨‍🍳 №{number} buyurtmangiz tayyorlanmoqda."
    if event == "READY":
        return (
            f"✅ №{number} buyurtmangiz tayyor! Olib ketishingiz mumkin."
            if pickup
            else f"✅ №{number} buyurtmangiz tayyor! Yaqin orada yo'lga chiqadi."
        )
    if event == "SERVED":
        return (
            f"🎉 №{number} buyurtma topshirildi. Yoqimli ishtaha!"
            if pickup
            else f"🎉 №{number} buyurtma yetkazildi. Yoqimli ishtaha!"
        )
    if event == "CANCELLED":
        contact = f" Savollar uchun: {restaurant_phone}" if restaurant_phone else ""
        return f"❌ №{number} buyurtma bekor qilindi.{contact}"
    return None


async def _send(restaurant_id: uuid.UUID, order_id: uuid.UUID, event: str) -> None:
    try:
        from app.services import orders as order_service

        async with SessionLocal() as session:
            order = await order_service.get_order(session, restaurant_id, order_id)
            if order.source != "TELEGRAM" or order.customer_id is None:
                return
            customer = await session.get(Customer, order.customer_id)
            restaurant = await session.get(Restaurant, restaurant_id)
            if customer is None or customer.telegram_user_id is None or not restaurant.telegram_bot_token:
                return
            text = _text(event, order.order_number, order.delivery_type, restaurant.phone)
            if text is None:
                return
            await telegram_api.send_message(restaurant.telegram_bot_token, customer.telegram_user_id, text)
    except Exception:  # noqa: BLE001 — blocked bot, network error, ...
        logger.warning("could not notify customer for order %s (%s)", order_id, event)


async def notify(restaurant_id: uuid.UUID, order_id: uuid.UUID, event: str) -> None:
    coro = _send(restaurant_id, order_id, event)
    if settings.print_dispatch_inline:  # tests: finish inside the request
        await coro
        return
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
