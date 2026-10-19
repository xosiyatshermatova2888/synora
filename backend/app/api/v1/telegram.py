"""Telegram webhook receiver — no auth dependency (Telegram calls this
directly), authenticated instead by `X-Telegram-Bot-Api-Secret-Token`
compared against the target restaurant's own stored secret with
`hmac.compare_digest` (same constant-time-compare style as `integrations/
payments/payme.py`'s Basic-auth check). Unlike Payme's webhook — whose
protocol *requires* every response to carry HTTP 200, errors encoded in the
body — Telegram has no such requirement: a genuinely unauthorized caller
(wrong/missing secret, unknown restaurant) gets a real 403/404 so Telegram
itself won't confuse it with a retryable delivery failure. A *successful*
delivery to a legitimate update always returns 200 regardless of what
happened inside `handle_update`, so Telegram never retries a call that was
actually received and processed."""

import hmac
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.restaurant import Restaurant
from app.services import telegram_bot as telegram_bot_service
from app.utils.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook/{restaurant_id}")
async def telegram_webhook(
    restaurant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    restaurant = await db.get(Restaurant, restaurant_id)
    if restaurant is None or not restaurant.telegram_webhook_secret:
        raise NotFoundError(detail="No bot configured for this restaurant.")

    secret_header = request.headers.get("x-telegram-bot-api-secret-token", "")
    if not hmac.compare_digest(secret_header, restaurant.telegram_webhook_secret):
        raise ForbiddenError(detail="Invalid webhook secret.")

    update = await request.json()
    await telegram_bot_service.handle_update(db, restaurant, update)
    return {"ok": True}
