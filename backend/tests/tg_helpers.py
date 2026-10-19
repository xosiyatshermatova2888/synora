"""Shared helpers for the Telegram bot tests: a recorder that stands in for the
Telegram HTTP client, and shortcuts that post updates to the webhook."""

from __future__ import annotations

import app.integrations.geocoding as geocoding
import app.integrations.storage as storage
import app.integrations.telegram as telegram_api
import app.services.media as media
import app.services.telegram_bot as bot
from tests.conftest import owner_headers

CHAT = {"id": 880001}
USER = {"id": 880001, "first_name": "Aziz", "last_name": "Karimov"}


class Recorder:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.photos: list[dict] = []
        self.edits: list[dict] = []
        self.markups: list[dict] = []
        self.sent_to: list[tuple[int, str]] = []

    def texts(self) -> list[str]:
        return [m["text"] for m in self.messages]

    def last_buttons(self) -> list[str]:
        for m in reversed(self.messages):
            kb = m.get("kb") or {}
            if "inline_keyboard" in kb:
                return [b["callback_data"] for row in kb["inline_keyboard"] for b in row if "callback_data" in b]
        return []


def install(monkeypatch, *, fail_photo: bool = False, address: str | None = "Navoiy, Xalqlar do'stligi ko'chasi 12") -> Recorder:
    rec = Recorder()

    async def send_message(token, chat_id, text, reply_markup=None, parse_mode=None):
        rec.messages.append({"text": text, "kb": reply_markup, "chat": chat_id})
        rec.sent_to.append((chat_id, text))
        return {}

    async def send_photo(token, chat_id, photo, caption=None, reply_markup=None, filename="photo.jpg", parse_mode=None):
        if fail_photo:
            raise telegram_api.TelegramError("wrong file type", 400)
        rec.photos.append({"photo": photo, "caption": caption, "kb": reply_markup})
        return {"photo": [{"file_id": "FILE-1"}, {"file_id": "FILE-LARGE"}]}

    async def edit_message_text(token, chat_id, message_id, text, reply_markup=None, parse_mode=None):
        rec.edits.append({"message_id": message_id, "text": text, "kb": reply_markup})
        return {}

    async def edit_reply_markup(token, chat_id, message_id, reply_markup):
        rec.markups.append({"message_id": message_id, "kb": reply_markup})
        return {}

    async def get_file_path(token, file_id):
        return "photos/receipt.jpg"

    async def download_file(token, file_path, max_bytes=0):
        return b"\xff\xd8receipt"

    async def save(data, filename):
        return f"/uploads/test/{filename}"

    async def fake_load(url):
        return b"\xff\xd8jpeg-bytes", "plov.jpg"

    async def fake_geocode(lat, lng):
        return address

    monkeypatch.setattr(telegram_api, "send_message", send_message)
    monkeypatch.setattr(telegram_api, "send_photo", send_photo)
    monkeypatch.setattr(telegram_api, "edit_message_text", edit_message_text)
    monkeypatch.setattr(telegram_api, "edit_message_reply_markup", edit_reply_markup)
    monkeypatch.setattr(telegram_api, "get_file_path", get_file_path)
    monkeypatch.setattr(telegram_api, "download_file", download_file)
    monkeypatch.setattr(storage, "save", save)
    monkeypatch.setattr(media, "load_image_bytes", fake_load)
    monkeypatch.setattr(geocoding, "reverse_geocode", fake_geocode)
    bot._FILE_IDS.clear()
    return rec


class Chat:
    """One customer's conversation, driven through the real webhook endpoint."""

    def __init__(self, client, world, secret: str, chat: dict = CHAT, user: dict = USER) -> None:
        self.client, self.world, self.secret, self.chat, self.user = client, world, secret, chat, user
        self.uid = 100

    def _post(self, **kw):
        self.uid += 1
        res = self.client.post(
            f"/api/v1/telegram/webhook/{self.world.restaurant_a.id}",
            headers={"X-Telegram-Bot-Api-Secret-Token": self.secret},
            json={"update_id": self.uid, **kw},
        )
        assert res.status_code == 200, res.text
        return res

    def msg(self, text=None, **extra):
        body = {"chat": self.chat, "from": self.user, **({"text": text} if text is not None else {}), **extra}
        return self._post(message=body)

    def tap(self, data, message_id=9, uid=None):
        if uid is not None:
            self.uid = uid - 1
        return self._post(callback_query={
            "id": f"cb{self.uid + 1}", "from": self.user,
            "message": {"chat": self.chat, "message_id": message_id}, "data": data,
        })


def make_product(client, world, name, price="10000.00", **extra):
    res = client.post(
        "/api/v1/menu/products",
        headers=owner_headers(world),
        json={"name": name, "price": price, "category_id": str(world.category_a.id), **extra},
    )
    assert res.status_code == 201, res.text
    return res.json()


def set_card(client, world, number="8600 1234 5678 9012", holder="SHIRIN TAOM"):
    res = client.patch(
        "/api/v1/restaurant/me", headers=owner_headers(world),
        json={"payment_card_number": number, "payment_card_holder": holder},
    )
    assert res.status_code == 200, res.text
