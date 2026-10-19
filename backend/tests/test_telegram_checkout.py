"""Telegram checkout: name -> phone -> delivery/pickup -> address (typed or
shared location) -> payment -> confirm, the order that results, the card-transfer
receipt, duplicate protection and status notifications to the customer."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.order import Order
from tests.conftest import owner_headers
from tests.test_telegram import _connect
from tests.tg_helpers import Chat, install, make_product, set_card


def _until_checkout(client, world, monkeypatch, **install_kw):
    secret = _connect(client, world, monkeypatch)
    rec = install(monkeypatch, **install_kw)
    osh = make_product(client, world, "Osh", "45000.00")
    chat = Chat(client, world, secret)
    chat.msg("/start")
    chat.tap(f"cat:{world.category_a.id}")
    chat.tap(f"prod:{osh['id']}")
    chat.tap(f"pq:{osh['id']}:2")
    chat.tap(f"pa:{osh['id']}:2")
    chat.tap("checkout")
    return chat, rec, osh


def _contact_and_delivery(chat):
    chat.msg("Aziz")
    chat.msg(contact={"phone_number": "+998 90 123-45-67"})
    chat.tap("dtype:DELIVERY")


async def _orders(db, world):
    return list((await db.scalars(select(Order).where(Order.restaurant_id == world.restaurant_a.id))).all())


class TestDeliveryWithSharedLocation:
    async def test_full_order_with_location_and_card_transfer(self, client, world, db, monkeypatch):
        set_card_after = None  # card is configured before the bot is used
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        set_card(client, world)
        chat.tap("ckedit")  # restart checkout now that a card exists
        _contact_and_delivery(chat)
        chat.tap("addr:loc")
        chat.msg(location={"latitude": 40.103, "longitude": 65.378})
        assert any("Navoiy, Xalqlar do'stligi ko'chasi 12" in t for t in rec.texts())  # exact address shown
        chat.tap("addr:ok")
        chat.msg("2-qavat, 5-xonadon")
        assert "pay:CARD_TRANSFER" in rec.last_buttons()
        chat.tap("pay:CARD_TRANSFER")
        summary = rec.texts()[-1]
        assert "Aziz" in summary and "+998901234567" in summary and "Xalqlar do'stligi" in summary
        chat.tap("confirm")

        orders = await _orders(db, world)
        assert len(orders) == 1
        order = orders[0]
        assert order.source == "TELEGRAM" and order.status == "OPEN" and order.kitchen_status == "NEW"
        assert order.customer_name == "Aziz" and order.customer_phone == "+998901234567"
        assert order.delivery_type == "DELIVERY"
        assert order.delivery_address == "Navoiy, Xalqlar do'stligi ko'chasi 12"
        assert (float(order.delivery_lat), float(order.delivery_lng)) == (40.103, 65.378)
        assert order.delivery_note == "2-qavat, 5-xonadon" and order.payment_method == "CARD_TRANSFER"
        assert order.table_id is None and str(order.total) == "90000.00"  # price fixed at purchase time
        confirmation = rec.texts()[-1]
        assert f"№ <b>{order.order_number}</b>" in confirmation
        assert "8600 1234 5678 9012" in confirmation and "SHIRIN TAOM" in confirmation  # card shown
        assert "chek" in confirmation.lower()

    async def test_order_is_visible_to_staff_with_address_and_phone(self, client, world, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        _contact_and_delivery(chat)
        chat.tap("addr:text")
        chat.msg("Navoiy sh., Tinchlik ko'chasi 7-uy")
        chat.tap("note:skip")
        chat.tap("pay:CASH")
        chat.tap("confirm")
        res = client.get("/api/v1/orders?limit=5", headers=owner_headers(world))
        order = res.json()["items"][0]  # appears without any manual approval
        assert order["status"] == "OPEN" and order["customer_phone"] == "+998901234567"
        assert order["delivery_address"] == "Navoiy sh., Tinchlik ko'chasi 7-uy"
        assert order["delivery_lat"] is None and order["payment_method"] == "CASH"

    async def test_unknown_address_asks_the_customer_to_type_it(self, client, world, db, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch, address=None)
        _contact_and_delivery(chat)
        chat.tap("addr:loc")
        chat.msg(location={"latitude": 40.1, "longitude": 65.3})
        assert "yozing" in rec.texts()[-1]
        chat.msg("Navoiy sh., Navoiy ko'chasi 3-uy")
        chat.tap("note:skip")
        chat.tap("pay:CASH")
        chat.tap("confirm")
        order = (await _orders(db, world))[0]
        assert order.delivery_address == "Navoiy sh., Navoiy ko'chasi 3-uy" and float(order.delivery_lat) == 40.1


class TestPickup:
    async def test_pickup_needs_no_address(self, client, world, db, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("90 123 45 67")
        chat.tap("dtype:PICKUP")
        assert "pay:CASH" in rec.last_buttons()
        chat.tap("pay:CASH")
        chat.tap("confirm")
        order = (await _orders(db, world))[0]
        assert order.delivery_type == "PICKUP" and order.delivery_address is None and order.customer_phone == "+998901234567"


class TestExpiredSubscription:
    async def test_lapsed_restaurant_takes_no_telegram_orders(self, client, world, db, monkeypatch):
        from datetime import datetime, timedelta, timezone

        import app.integrations.telegram as telegram_api

        alerts: list[str] = []

        async def answer(token, callback_query_id, text=None):
            alerts.append(text or "")

        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        monkeypatch.setattr(telegram_api, "answer_callback_query", answer)
        chat.msg("Aziz")
        chat.msg("90 123 45 67")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CASH")

        # Subscription ran out more than the 7-day grace ago while the customer was typing.
        world.restaurant_a.subscription_status = "ACTIVE"
        world.restaurant_a.current_period_end = datetime.now(timezone.utc) - timedelta(days=30)
        await db.commit()

        chat.tap("confirm")
        assert await _orders(db, world) == []
        assert any("buyurtma qabul qilinmaydi" in t for t in alerts), alerts


class TestValidation:
    def test_bad_phone_short_address_and_name_are_rejected(self, client, world, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("A")
        assert "to'g'ri yozing" in rec.texts()[-1]
        chat.msg("Aziz")
        chat.msg("12345")
        assert "noto'g'ri" in rec.texts()[-1]
        chat.msg("+998 90 123 45 67")
        chat.tap("dtype:DELIVERY")
        chat.tap("addr:text")
        chat.msg("uy 5")
        assert "qisqa" in rec.texts()[-1]

    def test_card_option_hidden_until_configured_payme_hidden_without_merchant(self, client, world, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        assert "pay:CARD_TRANSFER" not in rec.last_buttons() and "pay:PAYME" not in rec.last_buttons()

    def test_empty_cart_cannot_checkout(self, client, world, monkeypatch):
        secret = _connect(client, world, monkeypatch)
        rec = install(monkeypatch)
        chat = Chat(client, world, secret)
        chat.msg("/start")
        chat.tap("checkout")
        assert rec.texts()[-1] != "Aziz"  # no checkout prompt was sent
        assert not any("Ismingizni" in t for t in rec.texts())


class TestDuplicates:
    async def test_double_confirm_creates_one_order(self, client, world, db, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CASH")
        chat.tap("confirm")
        chat.tap("confirm")  # second tap, different update id
        chat.tap("confirm", uid=chat.uid + 1)
        assert len(await _orders(db, world)) == 1

    async def test_same_update_id_retry_is_idempotent(self, client, world, db, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CASH")
        chat.tap("confirm", uid=777)
        chat.tap("confirm", uid=777)  # Telegram redelivers the same update
        assert len(await _orders(db, world)) == 1


class TestReturningCustomer:
    def test_saved_name_and_phone_can_be_reused(self, client, world, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CASH")
        chat.tap("confirm")

        chat.tap(f"pa:{osh['id']}:1")
        chat.tap("checkout")
        assert "ckprev" in rec.last_buttons() and "+998901234567" in rec.texts()[-1]
        chat.tap("ckprev")
        assert "dtype:DELIVERY" in rec.last_buttons()  # straight to delivery type, no re-typing


class TestPaymentReceipt:
    async def test_customer_can_send_the_transfer_receipt(self, client, world, db, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        set_card(client, world)
        chat.tap("ckedit")
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CARD_TRANSFER")
        chat.tap("confirm")

        chat.msg(photo=[{"file_id": "small"}, {"file_id": "large"}])
        assert "Chek qabul qilindi" in rec.texts()[-1]
        order = (await _orders(db, world))[0]
        assert order.payment_proof_url and order.payment_proof_url.startswith("/uploads/test/proof_")

        # staff are told a receipt arrived, and a second photo is not re-attached
        notes = client.get("/api/v1/notifications", headers=owner_headers(world)).json()
        assert any("To'lov cheki" in n["title"] for n in notes)
        chat.msg(photo=[{"file_id": "again"}])
        assert "qabul qilinmadi" in rec.texts()[-1]

    async def test_photo_without_a_card_order_is_ignored(self, client, world, db, monkeypatch):
        secret = _connect(client, world, monkeypatch)
        rec = install(monkeypatch)
        chat = Chat(client, world, secret)
        chat.msg("/start")
        chat.msg(photo=[{"file_id": "x"}])
        assert "qabul qilinmadi" in rec.texts()[-1]


class TestStatusNotifications:
    async def test_customer_is_told_when_the_kitchen_moves_the_order(self, client, world, db, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        _contact_and_delivery(chat)
        chat.tap("addr:text")
        chat.msg("Navoiy sh., Tinchlik ko'chasi 7-uy")
        chat.tap("note:skip")
        chat.tap("pay:CASH")
        chat.tap("confirm")
        order = (await _orders(db, world))[0]

        def move(status):
            res = client.patch(
                f"/api/v1/orders/{order.id}/kitchen-status", headers=owner_headers(world), json={"kitchen_status": status}
            )
            assert res.status_code == 200, res.text
            return rec.sent_to[-1]

        chat_id, text = move("PREPARING")
        assert chat_id == 880001 and "tayyorlanmoqda" in text
        assert "yo'lga chiqadi" in move("READY")[1]
        assert "yetkazildi" in move("SERVED")[1]

    async def test_cancellation_is_sent_and_pickup_wording_differs(self, client, world, db, monkeypatch):
        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CASH")
        chat.tap("confirm")
        order = (await _orders(db, world))[0]
        client.patch(f"/api/v1/orders/{order.id}/kitchen-status", headers=owner_headers(world), json={"kitchen_status": "PREPARING"})
        client.patch(f"/api/v1/orders/{order.id}/kitchen-status", headers=owner_headers(world), json={"kitchen_status": "READY"})
        assert "Olib ketishingiz mumkin" in rec.sent_to[-1][1]
        client.patch(f"/api/v1/orders/{order.id}/status", headers=owner_headers(world), json={"status": "CANCELLED"})
        assert "bekor qilindi" in rec.sent_to[-1][1]

    async def test_a_dead_telegram_never_breaks_the_kitchen_action(self, client, world, db, monkeypatch):
        import app.integrations.telegram as telegram_api

        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CASH")
        chat.tap("confirm")
        order = (await _orders(db, world))[0]

        async def boom(*a, **k):
            raise telegram_api.TelegramError("Forbidden: bot was blocked by the user", 403)

        monkeypatch.setattr(telegram_api, "send_message", boom)
        res = client.patch(
            f"/api/v1/orders/{order.id}/kitchen-status", headers=owner_headers(world), json={"kitchen_status": "PREPARING"}
        )
        assert res.status_code == 200


class TestErrorsAreNotLeaked:
    def test_internal_failure_shows_a_generic_message(self, client, world, monkeypatch):
        import app.services.orders as order_service

        chat, rec, osh = _until_checkout(client, world, monkeypatch)
        chat.msg("Aziz")
        chat.msg("901234567")
        chat.tap("dtype:PICKUP")
        chat.tap("pay:CASH")

        async def broken(*a, **k):
            raise RuntimeError("secret internal detail: db password=hunter2")

        monkeypatch.setattr(order_service, "create_order", broken)
        import app.integrations.telegram as telegram_api

        answers = []

        async def answer(token, cid, text=None):
            answers.append(text)

        monkeypatch.setattr(telegram_api, "answer_callback_query", answer)
        chat.tap("confirm")
        assert answers and "hunter2" not in str(answers) and "xatolik" in answers[-1].lower()
