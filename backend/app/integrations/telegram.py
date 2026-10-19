"""Telegram Bot HTTP API client — one restaurant, one bot, one token (Section
3B). Deliberately thin: plain `httpx` calls against `https://api.telegram.org/
bot{token}/{method}`, no `aiogram`/`python-telegram-bot` framework. Every
restaurant's bot token is a request-time parameter, never module-level
config (unlike Payme, which is one global merchant account for the whole
deployment — see `integrations/payments/payme.py`).
"""

from __future__ import annotations

import json

import httpx

TELEGRAM_API_BASE = "https://api.telegram.org"
_TIMEOUT = httpx.Timeout(10.0)


class TelegramError(Exception):
    """A Telegram Bot API call returned `ok: false`."""

    def __init__(self, description: str, error_code: int | None = None):
        self.description = description
        self.error_code = error_code
        super().__init__(description)


async def _call(token: str, method: str, payload: dict | None = None, timeout: float | None = None) -> dict:
    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout) if timeout else _TIMEOUT) as client:
        response = await client.post(url, json=payload or {})
    body = response.json()
    if not body.get("ok"):
        raise TelegramError(body.get("description", "Unknown Telegram error"), body.get("error_code"))
    return body["result"]


async def get_me(token: str) -> dict:
    """Validates the token and returns the bot's own profile (id, username)."""
    return await _call(token, "getMe")


async def set_webhook(token: str, url: str, secret_token: str) -> None:
    await _call(
        token,
        "setWebhook",
        {"url": url, "secret_token": secret_token, "drop_pending_updates": True},
    )


async def get_updates(token: str, offset: int, timeout: int) -> list[dict]:
    """Long-poll for new updates (used when no public webhook URL exists)."""
    return await _call(
        token,
        "getUpdates",
        {"offset": offset, "timeout": timeout, "allowed_updates": ["message", "callback_query"]},
        timeout=timeout + 10,
    )


async def delete_webhook(token: str) -> None:
    await _call(token, "deleteWebhook", {"drop_pending_updates": True})


async def send_message(
    token: str, chat_id: int, text: str, reply_markup: dict | None = None, parse_mode: str | None = None
) -> dict:
    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return await _call(token, "sendMessage", payload)


async def edit_message_text(
    token: str, chat_id: int, message_id: int, text: str, reply_markup: dict | None = None, parse_mode: str | None = None
) -> dict:
    payload: dict = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return await _call(token, "editMessageText", payload)


async def edit_message_reply_markup(
    token: str, chat_id: int, message_id: int, reply_markup: dict
) -> dict:
    return await _call(
        token,
        "editMessageReplyMarkup",
        {"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup},
    )


async def get_file_path(token: str, file_id: str) -> str:
    return (await _call(token, "getFile", {"file_id": file_id}))["file_path"]


async def download_file(token: str, file_path: str, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    """Download a file a user sent to the bot (the token is part of the URL, so
    callers must never log it)."""
    url = f"{TELEGRAM_API_BASE}/file/bot{token}/{file_path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.get(url)
    if response.status_code != 200 or len(response.content) > max_bytes:
        raise TelegramError("Could not download file", response.status_code)
    return response.content


async def send_photo(
    token: str,
    chat_id: int,
    photo: bytes | str,
    caption: str | None = None,
    reply_markup: dict | None = None,
    filename: str = "photo.jpg",
    parse_mode: str | None = None,
) -> dict:
    """Send a photo by Telegram `file_id` (str) or by uploading its bytes."""
    fields: dict = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    if parse_mode:
        fields["parse_mode"] = parse_mode
    if isinstance(photo, str):
        fields["photo"] = photo
        if reply_markup is not None:
            fields["reply_markup"] = reply_markup
        return await _call(token, "sendPhoto", fields)

    data = {k: str(v) for k, v in fields.items()}
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendPhoto"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.post(url, data=data, files={"photo": (filename, photo)})
    body = response.json()
    if not body.get("ok"):
        raise TelegramError(body.get("description", "Unknown Telegram error"), body.get("error_code"))
    return body["result"]


async def answer_callback_query(token: str, callback_query_id: str, text: str | None = None) -> None:
    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    await _call(token, "answerCallbackQuery", payload)
