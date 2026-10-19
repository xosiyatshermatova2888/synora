"""Bot menu: product list, photo cards (uploaded by bytes, then cached by
file_id), quantity picker, pagination, editable cart, and the image guard."""

from __future__ import annotations

import app.services.media as media
import app.services.telegram_bot as bot
from tests.test_telegram import _connect
from tests.tg_helpers import Chat, install, make_product


def _open_category(client, world, monkeypatch, **install_kw):
    secret = _connect(client, world, monkeypatch)
    rec = install(monkeypatch, **install_kw)
    chat = Chat(client, world, secret)
    chat.msg("/start")
    return chat, rec


def _buttons(rec):
    kb = rec.messages[-1]["kb"]["inline_keyboard"]
    return [(b["text"], b["callback_data"]) for row in kb for b in row]


class TestMenuNavigation:
    def test_start_shows_categories_with_counts_and_a_menu_keyboard(self, client, world, monkeypatch):
        make_product(client, world, "Osh")
        chat, rec = _open_category(client, world, monkeypatch)
        assert any("xush kelibsiz" in t.lower() for t in rec.texts())
        assert rec.messages[0]["kb"]["keyboard"][0][0]["text"] == "🍽 Menyu"
        text, cb = _buttons(rec)[0]
        assert text.startswith("Mains (") and cb == f"cat:{world.category_a.id}"

    def test_category_lists_products_as_buttons_with_prices(self, client, world, monkeypatch):
        osh = make_product(client, world, "Osh", "45000.00")
        chat, rec = _open_category(client, world, monkeypatch)
        chat.tap(f"cat:{world.category_a.id}")
        listing = [(b["text"], b["callback_data"]) for row in rec.edits[-1]["kb"]["inline_keyboard"] for b in row]
        assert ("Osh — 45 000 UZS", f"prod:{osh['id']}") in listing
        assert rec.edits and rec.edits[-1]["message_id"] == 9  # navigation edits the tapped message in place

    def test_long_category_is_paginated(self, client, world, monkeypatch):
        for i in range(10):
            make_product(client, world, f"Taom {i}")
        chat, rec = _open_category(client, world, monkeypatch)
        chat.tap(f"cat:{world.category_a.id}")
        first = [b for b in rec.edits[-1]["kb"]["inline_keyboard"] if b[0]["callback_data"].startswith("prod:")]
        assert len(first) == 8 and "(1/2)" in rec.edits[-1]["text"]
        chat.tap(f"cat:{world.category_a.id}:1")
        second = [b for b in rec.edits[-1]["kb"]["inline_keyboard"] if b[0]["callback_data"].startswith("prod:")]
        assert len(second) == 2 and "(2/2)" in rec.edits[-1]["text"]


class TestProductCard:
    def test_card_has_photo_description_price_picker_and_add_button(self, client, world, monkeypatch):
        osh = make_product(client, world, "Osh", "45000.00", description="Guruch & go'sht <yangi>", image_url="/uploads/b/osh.jpg")
        chat, rec = _open_category(client, world, monkeypatch)
        chat.tap(f"prod:{osh['id']}")
        card = rec.photos[-1]
        assert card["photo"] == b"\xff\xd8jpeg-bytes"
        assert "<b>Osh</b>" in card["caption"] and "45 000 UZS" in card["caption"]
        assert "Guruch &amp; go'sht &lt;yangi&gt;" in card["caption"]  # HTML-escaped, apostrophes kept
        callbacks = [b["callback_data"] for row in card["kb"]["inline_keyboard"] for b in row]
        assert f"pq:{osh['id']}:2" in callbacks and f"pa:{osh['id']}:1" in callbacks

    def test_second_view_reuses_telegram_file_id(self, client, world, monkeypatch):
        osh = make_product(client, world, "Osh", image_url="/uploads/b/osh.jpg")
        chat, rec = _open_category(client, world, monkeypatch)
        chat.tap(f"prod:{osh['id']}")
        chat.tap(f"prod:{osh['id']}")
        assert rec.photos[0]["photo"] == b"\xff\xd8jpeg-bytes" and rec.photos[1]["photo"] == "FILE-LARGE"

    def test_photo_failure_falls_back_to_a_text_card(self, client, world, monkeypatch):
        osh = make_product(client, world, "Osh", image_url="/uploads/b/osh.jpg")
        chat, rec = _open_category(client, world, monkeypatch, fail_photo=True)
        chat.tap(f"prod:{osh['id']}")
        assert rec.photos == [] and "<b>Osh</b>" in rec.texts()[-1]

    def test_product_without_image_is_a_text_card(self, client, world, monkeypatch):
        choy = make_product(client, world, "Choy")
        chat, rec = _open_category(client, world, monkeypatch)
        chat.tap(f"prod:{choy['id']}")
        assert rec.photos == [] and "<b>Choy</b>" in rec.texts()[-1]

    def test_quantity_picker_updates_total_in_place(self, client, world, monkeypatch):
        osh = make_product(client, world, "Osh", "45000.00")
        chat, rec = _open_category(client, world, monkeypatch)
        chat.tap(f"pq:{osh['id']}:3")
        buttons = [b["text"] for row in rec.markups[-1]["kb"]["inline_keyboard"] for b in row]
        assert "3 ta" in buttons and any("135 000 UZS" in b for b in buttons)

    def test_add_with_quantity_merges_and_caps(self, client, world, monkeypatch):
        osh = make_product(client, world, "Osh", "1000.00")
        chat, rec = _open_category(client, world, monkeypatch)
        for _ in range(4):
            chat.tap(f"pa:{osh['id']}:20")
        chat.tap("cart")
        assert "50x Osh" in rec.texts()[-1]  # capped at 50 per product


class TestEditableCart:
    def test_plus_minus_remove(self, client, world, monkeypatch):
        osh = make_product(client, world, "Osh", "45000.00")
        chat, rec = _open_category(client, world, monkeypatch)
        chat.tap(f"pa:{osh['id']}:1")
        chat.tap("cart")
        chat.tap(f"inc:{osh['id']}")
        assert "2× Osh" in str(rec.edits[-1]["kb"]) and "90 000 UZS" in rec.edits[-1]["text"]
        chat.tap(f"dec:{osh['id']}")
        chat.tap(f"dec:{osh['id']}")  # quantity 0 -> removed
        assert "bo'sh" in rec.edits[-1]["text"]


class TestImageGuard:
    def test_own_storage_paths_are_allowed(self, monkeypatch):
        monkeypatch.setattr(media.settings, "s3_endpoint", "http://minio:9000")
        assert media._storage_url("/uploads/synora/a.jpg") == "http://minio:9000/synora/a.jpg"
        assert media._storage_url("http://localhost:9000/synora/a.jpg") == "http://minio:9000/synora/a.jpg"

    def test_arbitrary_urls_are_refused(self, monkeypatch):
        monkeypatch.setattr(media.settings, "s3_endpoint", "http://minio:9000")
        for url in ("http://169.254.169.254/latest/meta-data", "http://evil.example/x.jpg", "file:///etc/passwd", "relative.jpg"):
            assert media._storage_url(url) is None

    async def test_local_files_cannot_escape_the_upload_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(media.settings, "upload_dir", str(tmp_path))
        (tmp_path / "ok.jpg").write_bytes(b"x")
        assert await media.load_image_bytes("/files/ok.jpg") == (b"x", "ok.jpg")
        assert await media.load_image_bytes("/files/../secret.txt") is None


class TestFormatting:
    def test_money_groups_thousands(self):
        assert bot._money("45000.00", "UZS") == "45 000 UZS"
        assert bot._money("12.50", "UZS") == "12.50 UZS"
