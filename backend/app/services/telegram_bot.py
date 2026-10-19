"""Telegram ordering bot — one bot per restaurant (Section 3B).

`connect_bot`/`disconnect_bot` manage the Restaurant's own bot registration.
`handle_update` is the conversation state machine, backed by
`TelegramSession` (DB-persisted, not in-memory) — the flow mirrors the
spec's START -> Menu -> Category -> Product -> Cart -> Table number ->
Confirm order exactly, but as inline-keyboard button taps rather than typed
text, so there's no free-text parsing to get wrong. Products with *required*
modifier groups are left out of the bot's catalog (stated scope cut — the
QR menu, `services/public_menu.py`, already covers that case in full).
"""

from __future__ import annotations

import secrets
import html
import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.services.subscription import ensure_can_write
from app.utils.errors import PaymentRequiredError
from app.core.config import settings
from app.database.session import SessionLocal
from app.integrations import geocoding
from app.integrations import storage
from app.integrations import telegram as telegram_api
from app.services import media as media_service
from app.models.branch import Branch
from app.models.restaurant import Restaurant
from app.models.telegram_session import TelegramSession
from app.schemas.orders import OrderCreate, OrderItemIn
from app.services import customers as customers_service
from app.services import orders as order_service
from app.services import payme_payments
from app.services import public_menu as public_menu_service
from app.utils.errors import BusinessRuleError
from app.utils.phone import normalize_uz_phone

WEBHOOK_URL_TEMPLATE = "{base}/api/v1/telegram/webhook/{restaurant_id}"


async def connect_bot(session: AsyncSession, restaurant_id: uuid.UUID, token: str) -> Restaurant:
    restaurant = await session.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise BusinessRuleError(detail="Restaurant not found.")

    me = await telegram_api.get_me(token)  # raises TelegramError if the token is invalid

    webhook_secret = secrets.token_urlsafe(32)
    if settings.public_app_url and settings.public_app_url != "http://localhost:3000":
        url = WEBHOOK_URL_TEMPLATE.format(base=settings.public_app_url.rstrip("/"), restaurant_id=restaurant_id)
        await telegram_api.set_webhook(token, url, webhook_secret)
    # else: local dev has no publicly reachable URL — token is still saved so
    # the connection can be verified/tested (e.g. via a hand-crafted webhook
    # POST), but Telegram itself won't be told to call back yet.

    restaurant.telegram_bot_token = token
    restaurant.telegram_bot_username = me.get("username")
    restaurant.telegram_webhook_secret = webhook_secret
    await session.commit()
    return restaurant


def _webhook_base() -> str | None:
    base = (settings.public_app_url or "").rstrip("/")
    # Telegram only delivers to public HTTPS URLs.
    return base if base.startswith("https://") else None


async def register_all_webhooks() -> None:
    """Best-effort, at startup in webhook mode: make Telegram call THIS server
    for every connected restaurant bot. Never raises — a Telegram outage must not
    stop the API from starting."""
    base = _webhook_base()
    if base is None:
        return
    try:
        async with SessionLocal() as session:
            restaurants = (
                await session.scalars(select(Restaurant).where(Restaurant.telegram_bot_token.is_not(None)))
            ).all()
            for restaurant in restaurants:
                try:
                    secret = restaurant.telegram_webhook_secret or secrets.token_urlsafe(32)
                    await telegram_api.set_webhook(
                        restaurant.telegram_bot_token,
                        WEBHOOK_URL_TEMPLATE.format(base=base, restaurant_id=restaurant.id),
                        secret,
                    )
                    if restaurant.telegram_webhook_secret != secret:
                        restaurant.telegram_webhook_secret = secret
                        await session.commit()
                    logger.info("telegram webhook registered", extra={"restaurant_id": str(restaurant.id)})
                except Exception:  # noqa: BLE001
                    logger.exception("could not register telegram webhook for restaurant %s", restaurant.id)
    except Exception:  # noqa: BLE001
        logger.exception("telegram webhook registration failed")


async def disconnect_bot(session: AsyncSession, restaurant_id: uuid.UUID) -> Restaurant:
    restaurant = await session.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise BusinessRuleError(detail="Restaurant not found.")

    if restaurant.telegram_bot_token:
        try:
            await telegram_api.delete_webhook(restaurant.telegram_bot_token)
        except Exception:
            pass  # best-effort — the local record is cleared regardless

    restaurant.telegram_bot_token = None
    restaurant.telegram_bot_username = None
    restaurant.telegram_webhook_secret = None
    await session.commit()
    return restaurant


# ---------------------------------------------------------------------------
# Conversation state machine
# ---------------------------------------------------------------------------
logger = logging.getLogger("synora.telegram_bot")

PAGE_SIZE = 8
MAX_QTY = 20
MAX_CART_QTY = 50
# (restaurant_id, image_url) -> Telegram file_id. A file_id is specific to one
# bot, so it is keyed by restaurant; it lets repeat views skip the re-upload.
_FILE_IDS: dict[tuple[uuid.UUID, str], str] = {}

MAIN_KEYBOARD = {
    "keyboard": [[{"text": "🍽 Menyu"}, {"text": "🛒 Savat"}]],
    "resize_keyboard": True,
}
PAYMENT_LABELS = {
    "CASH": "💵 Naqd pul",
    "CARD_TRANSFER": "💳 Karta orqali o'tkazma",
    "PAYME": "🟦 Payme (onlayn)",
}
GENERIC_ERROR = "Kechirasiz, xatolik yuz berdi. Iltimos, qayta urinib ko'ring."


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _money(value: Decimal | str, currency: str) -> str:
    amount = Decimal(str(value))
    text = f"{int(amount):,}".replace(",", " ") if amount == amount.to_integral_value() else f"{amount:,.2f}".replace(",", " ")
    return f"{text} {currency}"


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": text, "callback_data": data} for text, data in row] for row in rows]}


def _maps_url(lat, lng) -> str:
    return f"https://www.google.com/maps?q={lat},{lng}"


async def _say(restaurant: Restaurant, chat_id: int, text: str, markup: dict | None = None, html_mode: bool = False) -> None:
    await telegram_api.send_message(
        restaurant.telegram_bot_token, chat_id, text, markup, parse_mode="HTML" if html_mode else None
    )


async def _send_or_edit(
    restaurant: Restaurant, chat_id: int, message_id: int | None, text: str, markup: dict, html_mode: bool = False
) -> None:
    """Edit the tapped message in place (keeps the chat tidy); fall back to a
    new message when it can't be edited (e.g. it was a photo card)."""
    token = restaurant.telegram_bot_token
    if message_id is not None:
        try:
            await telegram_api.edit_message_text(token, chat_id, message_id, text, markup, parse_mode="HTML" if html_mode else None)
            return
        except Exception:  # noqa: BLE001
            pass
    await _say(restaurant, chat_id, text, markup, html_mode)


def _state(tg_session: TelegramSession) -> dict:
    return dict(tg_session.state or {})


async def _save(session: AsyncSession, tg_session: TelegramSession, **changes) -> dict:
    state = _state(tg_session)
    for key, value in changes.items():
        if value is None:
            state.pop(key, None)
        else:
            state[key] = value
    tg_session.state = state
    flag_modified(tg_session, "state")
    await session.commit()
    return state


async def _get_or_create_session(session: AsyncSession, restaurant_id: uuid.UUID, chat_id: int) -> TelegramSession:
    tg_session = await session.get(TelegramSession, chat_id)
    if tg_session is None:
        tg_session = TelegramSession(chat_id=chat_id, restaurant_id=restaurant_id, state={})
        session.add(tg_session)
        await session.flush()
    return tg_session


async def _active_branches(session: AsyncSession, restaurant_id: uuid.UUID) -> list[Branch]:
    return list(
        (
            await session.scalars(
                select(Branch).where(Branch.restaurant_id == restaurant_id, Branch.is_active.is_(True)).order_by(Branch.name)
            )
        ).all()
    )


async def _sellable_categories(session: AsyncSession, restaurant: Restaurant) -> list[dict]:
    """Public menu, with products that carry a *required* modifier group
    filtered out (bot scope cut) and now-empty categories dropped."""
    menu = await public_menu_service.get_public_menu(session, restaurant.slug)
    categories = []
    for cat in menu["categories"]:
        products = [p for p in cat["products"] if not any(g.is_required for g in p.modifier_groups)]
        if products:
            categories.append({"id": cat["id"], "name": cat["name"], "products": products})
    return categories


def _find_product(categories: list[dict], product_id: str):
    for cat in categories:
        for product in cat["products"]:
            if str(product.id) == product_id:
                return cat, product
    return None, None


def _cart_summary(cart: list[dict]) -> tuple[str, Decimal]:
    total = Decimal("0.00")
    lines = []
    for item in cart:
        line_total = Decimal(str(item["price"])) * item["quantity"]
        total += line_total
        lines.append(f"{item['quantity']}x {item['name']} — {line_total}")
    return "\n".join(lines), total


# ---------------------------------------------------------------------------
# Update routing
# ---------------------------------------------------------------------------
async def handle_update(session: AsyncSession, restaurant: Restaurant, update: dict) -> None:
    token = restaurant.telegram_bot_token
    if not token:
        return

    message = update.get("message")
    callback = update.get("callback_query")

    if message:
        chat_id = message["chat"]["id"]
        try:
            await _handle_message(session, restaurant, chat_id, message)
        except Exception:  # noqa: BLE001 — never leak internals to a customer
            logger.exception("telegram message handling failed")
            await session.rollback()
            try:
                await _say(restaurant, chat_id, GENERIC_ERROR)
            except Exception:  # noqa: BLE001
                pass
        return

    if callback:
        chat_id = callback["message"]["chat"]["id"]
        data = callback.get("data", "")
        # \`update_id\` is per-bot and monotonically increasing, so it doubles as a
        # stable Idempotency-Key if Telegram retries a delivery.
        idempotency_key = f"tg-{update.get('update_id')}" if update.get("update_id") is not None else None
        try:
            toast = await _handle_callback(
                session, restaurant, chat_id, data, idempotency_key, message_id=callback["message"].get("message_id"),
                from_user=callback.get("from") or {},
            )
        except Exception:  # noqa: BLE001
            logger.exception("telegram callback handling failed (%s)", data.split(":", 1)[0])
            await session.rollback()
            toast = GENERIC_ERROR
        try:
            await telegram_api.answer_callback_query(token, callback["id"], text=toast)
        except Exception:  # noqa: BLE001 — expired callback queries are normal
            pass


async def _handle_message(session: AsyncSession, restaurant: Restaurant, chat_id: int, message: dict) -> None:
    text = (message.get("text") or "").strip()
    from_user = message.get("from") or {}

    if text.startswith("/start"):
        await _start(session, restaurant, chat_id, from_user)
        return
    if text in ("/menu", "🍽 Menyu"):
        tg = await _get_or_create_session(session, restaurant.id, chat_id)
        await _show_categories(session, restaurant, chat_id, tg.branch_id)
        return
    if text in ("/cart", "🛒 Savat"):
        tg = await _get_or_create_session(session, restaurant.id, chat_id)
        await _render_cart(restaurant, chat_id, _state(tg).get("cart", []))
        return

    tg = await _get_or_create_session(session, restaurant.id, chat_id)
    step = _state(tg).get("step")

    if message.get("contact") and step == "phone":
        await _got_phone(session, restaurant, chat_id, tg, message["contact"].get("phone_number"))
    elif message.get("location") and step in ("address_choice", "address_text"):
        await _got_location(session, restaurant, chat_id, tg, message["location"])
    elif message.get("photo") or (message.get("document") or {}).get("mime_type", "").startswith("image/"):
        await _got_photo(session, restaurant, chat_id, tg, message)
    elif text and step == "name":
        await _got_name(session, restaurant, chat_id, tg, text)
    elif text and step == "phone":
        await _got_phone(session, restaurant, chat_id, tg, text)
    elif text and step in ("address_text", "address_choice"):
        await _got_address_text(session, restaurant, chat_id, tg, text)
    elif text and step == "address_note":
        await _got_note(session, restaurant, chat_id, tg, text)
    else:
        await _say(restaurant, chat_id, "Menyuni ochish uchun pastdagi 🍽 Menyu tugmasini bosing.", MAIN_KEYBOARD)


async def _handle_callback(
    session: AsyncSession,
    restaurant: Restaurant,
    chat_id: int,
    data: str,
    idempotency_key: str | None = None,
    message_id: int | None = None,
    from_user: dict | None = None,
) -> str | None:
    tg = await _get_or_create_session(session, restaurant.id, chat_id)
    state = _state(tg)
    cart: list[dict] = state.get("cart", [])
    action, _, rest = data.partition(":")

    if action == "noop":
        return None
    if action == "branch":
        await _show_categories(session, restaurant, chat_id, uuid.UUID(rest), message_id)
        return None
    if action == "menu":
        await _show_categories(session, restaurant, chat_id, tg.branch_id, message_id)
        return None
    if action == "cat":
        category_id, _, page = rest.partition(":")
        await _show_products(session, restaurant, chat_id, category_id, int(page) if page.isdigit() else 0, message_id)
        return None
    if action == "prod":
        await _show_product(session, restaurant, chat_id, rest)
        return None
    if action == "pq":  # change quantity on a product card
        product_id, _, qty = rest.partition(":")
        qty = min(max(int(qty or 1), 1), MAX_QTY)
        categories = await _sellable_categories(session, restaurant)
        cat, product = _find_product(categories, product_id)
        if product is None:
            return "Mahsulot topilmadi."
        await _update_card_keyboard(restaurant, chat_id, message_id, product, str(cat["id"]), qty)
        return None
    if action == "pa":  # add (qty) to cart from a product card
        product_id, _, qty = rest.partition(":")
        qty = min(max(int(qty or 1), 1), MAX_QTY)
        categories = await _sellable_categories(session, restaurant)
        cat, product = _find_product(categories, product_id)
        if product is None:
            return "Mahsulot topilmadi."
        existing = next((i for i in cart if i["product_id"] == product_id), None)
        if existing:
            existing["quantity"] = min(existing["quantity"] + qty, MAX_CART_QTY)
        else:
            cart.append({"product_id": product_id, "name": product.name, "price": str(product.price), "quantity": qty})
        await _save(session, tg, cart=cart)
        if message_id is not None:
            try:
                await telegram_api.edit_message_reply_markup(
                    restaurant.telegram_bot_token, chat_id, message_id,
                    _kb([[("🛒 Savatni ko'rish", "cart"), ("🍽 Davom etish", f"cat:{cat['id']}")]]),
                )
            except Exception:  # noqa: BLE001
                pass
        _, total = _cart_summary(cart)
        return f"✅ Savatga qo'shildi. Jami: {_money(total, restaurant.currency)}"
    if action == "cart":
        await _render_cart(restaurant, chat_id, cart)
        return None
    if action in ("inc", "dec", "del"):
        item = next((i for i in cart if i["product_id"] == rest), None)
        if item is None:
            return "Mahsulot savatda yo'q."
        if action == "inc":
            item["quantity"] = min(item["quantity"] + 1, MAX_CART_QTY)
        elif action == "dec":
            item["quantity"] -= 1
        if action == "del" or item["quantity"] <= 0:
            cart = [i for i in cart if i["product_id"] != rest]
        await _save(session, tg, cart=cart)
        await _render_cart(restaurant, chat_id, cart, edit_message_id=message_id)
        return None
    if action == "clear":
        await _save(session, tg, cart=[], step=None)
        await _render_cart(restaurant, chat_id, [], edit_message_id=message_id)
        return "Savat tozalandi."

    # ---- checkout ----
    if action == "checkout":
        if not cart:
            return "Avval mahsulot tanlang."
        await _begin_checkout(session, restaurant, chat_id, tg, from_user or {})
        return None
    if action == "ckname":
        await _got_name(session, restaurant, chat_id, tg, state.get("suggested_name") or "")
        return None
    if action == "ckprev":  # reuse saved contact details
        await _after_contact(session, restaurant, chat_id, tg)
        return None
    if action == "ckedit":
        await _ask_name(session, restaurant, chat_id, tg, from_user or {})
        return None
    if action == "dtype":
        await _got_delivery_type(session, restaurant, chat_id, tg, rest)
        return None
    if action == "addr":
        await _got_address_choice(session, restaurant, chat_id, tg, rest)
        return None
    if action == "note":
        await _got_note(session, restaurant, chat_id, tg, "")
        return None
    if action == "pay":
        await _got_payment(session, restaurant, chat_id, tg, rest)
        return None
    if action == "ckcancel":
        await _save(session, tg, step=None, name=None, phone=None, delivery_type=None, address=None,
                    lat=None, lng=None, note=None, payment_method=None)
        await _say(restaurant, chat_id, "Buyurtma bekor qilindi. Savat saqlandi.", MAIN_KEYBOARD)
        return None
    if action == "confirm":
        return await _confirm_order(session, restaurant, chat_id, tg, idempotency_key)
    return None


# ---------------------------------------------------------------------------
# Menu: categories -> products -> product card
# ---------------------------------------------------------------------------
async def _start(session: AsyncSession, restaurant: Restaurant, chat_id: int, from_user: dict) -> None:
    tg = await _get_or_create_session(session, restaurant.id, chat_id)
    await _save(session, tg, cart=[], step=None)
    tg.branch_id = None
    await customers_service.find_or_create(
        session,
        restaurant.id,
        telegram_user_id=chat_id,
        full_name=(f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}").strip() or None,
    )
    await session.commit()

    await _say(
        restaurant,
        chat_id,
        f"Assalomu alaykum! 👋\n<b>{_esc(restaurant.name)}</b> buyurtma botiga xush kelibsiz.\n"
        "Taom tanlang, savatga soling va buyurtma bering.",
        MAIN_KEYBOARD,
        html_mode=True,
    )
    branches = await _active_branches(session, restaurant.id)
    if len(branches) > 1:
        rows = [[(b.name, f"branch:{b.id}")] for b in branches]
        await _say(restaurant, chat_id, "Filialni tanlang:", _kb(rows))
    elif branches:
        await _show_categories(session, restaurant, chat_id, branches[0].id)
    else:
        await _say(restaurant, chat_id, "Hozircha faol filial yo'q.")


async def _show_categories(
    session: AsyncSession, restaurant: Restaurant, chat_id: int, branch_id: uuid.UUID | None, message_id: int | None = None
) -> None:
    tg = await _get_or_create_session(session, restaurant.id, chat_id)
    if branch_id is None:
        branches = await _active_branches(session, restaurant.id)
        branch_id = branches[0].id if branches else None
    if branch_id is None:
        await _say(restaurant, chat_id, "Hozircha faol filial yo'q.")
        return
    tg.branch_id = branch_id
    await session.commit()

    categories = await _sellable_categories(session, restaurant)
    if not categories:
        await _say(restaurant, chat_id, "Menyu hozircha bo'sh.")
        return
    rows = [[(f"{c['name']} ({len(c['products'])})", f"cat:{c['id']}")] for c in categories]
    rows.append([("🛒 Savat", "cart")])
    await _send_or_edit(restaurant, chat_id, message_id, "🍽 <b>Menyu</b>\nKategoriyani tanlang:", _kb(rows), html_mode=True)


async def _show_products(
    session: AsyncSession, restaurant: Restaurant, chat_id: int, category_id: str, page: int = 0, message_id: int | None = None
) -> None:
    categories = await _sellable_categories(session, restaurant)
    category = next((c for c in categories if str(c["id"]) == category_id), None)
    if category is None:
        await _say(restaurant, chat_id, "Kategoriya topilmadi.")
        return

    products = category["products"]
    pages = max(1, (len(products) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    title = f"<b>{_esc(category['name'])}</b>" + (f"  ({page + 1}/{pages})" if pages > 1 else "")
    rows = [
        [(f"{p.name} — {_money(p.price, restaurant.currency)}", f"prod:{p.id}")]
        for p in products[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    ]
    nav: list[tuple[str, str]] = []
    if page > 0:
        nav.append(("⬅️ Oldingi", f"cat:{category_id}:{page - 1}"))
    if page < pages - 1:
        nav.append(("Keyingi ➡️", f"cat:{category_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("⬅️ Kategoriyalar", "menu"), ("🛒 Savat", "cart")])
    await _send_or_edit(restaurant, chat_id, message_id, f"{title}\nTaomni tanlang:", _kb(rows), html_mode=True)


def _product_caption(product, currency: str) -> str:
    parts = [f"<b>{_esc(product.name)}</b>"]
    if product.description:
        parts.append(_esc(product.description.strip())[:600])
    parts.append(f"💰 {_esc(_money(product.price, currency))}")
    return "\n".join(parts)


def _card_keyboard(product, category_id: str, qty: int, currency: str) -> dict:
    total = _money(Decimal(str(product.price)) * qty, currency)
    return _kb(
        [
            [("➖", f"pq:{product.id}:{max(1, qty - 1)}"), (f"{qty} ta", "noop"), ("➕", f"pq:{product.id}:{min(MAX_QTY, qty + 1)}")],
            [(f"🛒 Savatga qo'shish · {total}", f"pa:{product.id}:{qty}")],
            [("⬅️ Orqaga", f"cat:{category_id}")],
        ]
    )


async def _update_card_keyboard(
    restaurant: Restaurant, chat_id: int, message_id: int | None, product, category_id: str, qty: int
) -> None:
    if message_id is None:
        return
    try:
        await telegram_api.edit_message_reply_markup(
            restaurant.telegram_bot_token, chat_id, message_id, _card_keyboard(product, category_id, qty, restaurant.currency)
        )
    except Exception:  # noqa: BLE001 — "message is not modified" etc.
        pass


async def _show_product(session: AsyncSession, restaurant: Restaurant, chat_id: int, product_id: str) -> None:
    categories = await _sellable_categories(session, restaurant)
    cat, product = _find_product(categories, product_id)
    token = restaurant.telegram_bot_token
    if product is None:
        await _say(restaurant, chat_id, "Mahsulot topilmadi.")
        return
    caption = _product_caption(product, restaurant.currency)
    keyboard = _card_keyboard(product, str(cat["id"]), 1, restaurant.currency)
    if product.image_url:
        key = (restaurant.id, product.image_url)
        try:
            file_id = _FILE_IDS.get(key)
            if file_id:
                await telegram_api.send_photo(token, chat_id, file_id, caption, keyboard, parse_mode="HTML")
                return
            loaded = await media_service.load_image_bytes(product.image_url)
            if loaded is not None:
                result = await telegram_api.send_photo(
                    token, chat_id, loaded[0], caption, keyboard, filename=loaded[1], parse_mode="HTML"
                )
                photos = (result or {}).get("photo") or []
                if photos:
                    _FILE_IDS[key] = photos[-1]["file_id"]
                return
        except Exception:  # noqa: BLE001 — fall back to a text card
            _FILE_IDS.pop(key, None)
            logger.warning("photo card failed for product %s; sending text", product.id)
    await _say(restaurant, chat_id, caption, keyboard, html_mode=True)


async def _render_cart(
    restaurant: Restaurant, chat_id: int, cart: list[dict], edit_message_id: int | None = None
) -> None:
    if not cart:
        text, rows = "🛒 Savat bo'sh.", [[("🍽 Menyu", "menu")]]
    else:
        lines, total = _cart_summary(cart)
        text = f"🛒 Savatingiz:\n\n{lines}\n\nJami: {_money(total, restaurant.currency)}"
        rows = [
            [("➖", f"dec:{i['product_id']}"), (f"{i['quantity']}× {i['name']}"[:28], "noop"),
             ("➕", f"inc:{i['product_id']}"), ("🗑", f"del:{i['product_id']}")]
            for i in cart
        ]
        rows += [[("✅ Buyurtma berish", "checkout")], [("🍽 Menyu", "menu"), ("🗑 Tozalash", "clear")]]
    await _send_or_edit(restaurant, chat_id, edit_message_id, text, _kb(rows))


# ---------------------------------------------------------------------------
# Checkout: name -> phone -> delivery type -> address -> payment -> confirm
# ---------------------------------------------------------------------------
async def _begin_checkout(
    session: AsyncSession, restaurant: Restaurant, chat_id: int, tg: TelegramSession, from_user: dict
) -> None:
    await _save(session, tg, checkout_id=uuid.uuid4().hex, name=None, phone=None, delivery_type=None,
                address=None, lat=None, lng=None, note=None, payment_method=None)
    customer = await customers_service.find_or_create(session, restaurant.id, telegram_user_id=chat_id)
    if customer.phone and customer.full_name:
        await _save(session, tg, step="reuse", name=customer.full_name, phone=customer.phone)
        await _say(
            restaurant, chat_id,
            f"Oldingi ma'lumotlaringiz:\n👤 {customer.full_name}\n📱 {customer.phone}\n\nShulardan foydalanamizmi?",
            _kb([[("✅ Ha, shular", "ckprev")], [("✏️ O'zgartirish", "ckedit")]]),
        )
        return
    await _ask_name(session, restaurant, chat_id, tg, from_user)


async def _ask_name(
    session: AsyncSession, restaurant: Restaurant, chat_id: int, tg: TelegramSession, from_user: dict
) -> None:
    suggested = (f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}").strip()
    await _save(session, tg, step="name", suggested_name=suggested or None)
    rows = [[(f"✅ {suggested[:40]}", "ckname")]] if suggested else []
    rows.append([("❌ Bekor qilish", "ckcancel")])
    await _say(restaurant, chat_id, "👤 Ismingizni yozing:", _kb(rows))


async def _got_name(session, restaurant, chat_id, tg, text: str) -> None:
    name = " ".join(text.split())
    if not 2 <= len(name) <= 60:
        await _say(restaurant, chat_id, "Iltimos, ismingizni to'g'ri yozing (2–60 harf).")
        return
    await _save(session, tg, name=name, step="phone")
    await _say(
        restaurant, chat_id,
        "📱 Telefon raqamingizni yuboring.\nPastdagi tugmani bosing yoki raqamni yozing (masalan: 90 123 45 67).",
        {"keyboard": [[{"text": "📱 Raqamimni yuborish", "request_contact": True}]],
         "resize_keyboard": True, "one_time_keyboard": True},
    )


async def _got_phone(session, restaurant, chat_id, tg, raw: str | None) -> None:
    phone = normalize_uz_phone(raw)
    if phone is None:
        await _say(restaurant, chat_id, "❗ Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67 yoki 90 123 45 67.")
        return
    await _save(session, tg, phone=phone)
    customer = await customers_service.find_or_create(session, restaurant.id, telegram_user_id=chat_id)
    state = _state(tg)
    if not customer.phone:
        customer.phone = phone
    if state.get("name") and not customer.full_name:
        customer.full_name = state["name"]
    await session.commit()
    await _say(restaurant, chat_id, f"✅ {phone}", MAIN_KEYBOARD)
    await _after_contact(session, restaurant, chat_id, tg)


async def _after_contact(session, restaurant, chat_id, tg) -> None:
    await _save(session, tg, step="delivery_type")
    await _say(
        restaurant, chat_id, "Buyurtmani qanday olasiz?",
        _kb([[("🚚 Yetkazib berish", "dtype:DELIVERY")], [("🏃 O'zim olib ketaman", "dtype:PICKUP")],
             [("❌ Bekor qilish", "ckcancel")]]),
    )


async def _got_delivery_type(session, restaurant, chat_id, tg, kind: str) -> None:
    if kind not in ("DELIVERY", "PICKUP"):
        return
    await _save(session, tg, delivery_type=kind, address=None, lat=None, lng=None, note=None)
    if kind == "PICKUP":
        await _ask_payment(session, restaurant, chat_id, tg)
        return
    await _save(session, tg, step="address_choice")
    await _say(
        restaurant, chat_id,
        "📍 Yetkazib berish manzilini qanday kiritasiz?",
        _kb([[("📍 Lokatsiya yuborish", "addr:loc")], [("✍️ Manzilni yozaman", "addr:text")]]),
    )


async def _got_address_choice(session, restaurant, chat_id, tg, choice: str) -> None:
    if choice == "ok":
        if _state(tg).get("address"):
            await _ask_note(session, restaurant, chat_id, tg)
        return
    if choice == "loc":
        await _save(session, tg, step="address_choice")
        await _say(
            restaurant, chat_id,
            "Pastdagi tugmani bosib joylashuvingizni yuboring (yoki 📎 → Joylashuv):",
            {"keyboard": [[{"text": "📍 Joylashuvni yuborish", "request_location": True}], [{"text": "🍽 Menyu"}]],
             "resize_keyboard": True, "one_time_keyboard": True},
        )
    else:
        await _save(session, tg, step="address_text")
        await _say(
            restaurant, chat_id,
            "✍️ Aniq manzilni yozing: shahar/tuman, ko'cha, uy raqami (mo'ljal bo'lsa qo'shing).\n"
            "Masalan: Navoiy sh., Xalqlar do'stligi ko'chasi 12-uy",
        )


async def _got_location(session, restaurant, chat_id, tg, location: dict) -> None:
    lat, lng = location.get("latitude"), location.get("longitude")
    if lat is None or lng is None:
        return
    address = await geocoding.reverse_geocode(float(lat), float(lng))
    await _save(session, tg, lat=round(float(lat), 6), lng=round(float(lng), 6), address=address, step="address_text")
    await _say(restaurant, chat_id, "📍 Joylashuv qabul qilindi.", MAIN_KEYBOARD)
    if address:
        await _say(
            restaurant, chat_id,
            f"Aniqlangan manzil:\n<b>{_esc(address)}</b>\n\nTo'g'rimi?",
            _kb([[("✅ Ha, to'g'ri", "addr:ok")], [("✍️ O'zim yozaman", "addr:text")]]),
            html_mode=True,
        )
    else:
        await _say(
            restaurant, chat_id,
            "Manzilni avtomatik aniqlab bo'lmadi. Iltimos, aniq manzilni yozing (ko'cha, uy raqami):",
        )


async def _got_address_text(session, restaurant, chat_id, tg, text: str) -> None:
    address = " ".join(text.split())
    if not 8 <= len(address) <= 300:
        await _say(restaurant, chat_id, "❗ Manzil juda qisqa. Ko'cha va uy raqamini yozing.")
        return
    await _save(session, tg, address=address)
    await _ask_note(session, restaurant, chat_id, tg)


async def _ask_note(session, restaurant, chat_id, tg) -> None:
    await _save(session, tg, step="address_note")
    await _say(
        restaurant, chat_id,
        "🏢 Qo'shimcha ma'lumot: kvartira, qavat, kirish eshigi yoki mo'ljal (ixtiyoriy).",
        _kb([[("Keyingisi ➡️", "note:skip")]]),
    )


async def _got_note(session, restaurant, chat_id, tg, text: str) -> None:
    note = " ".join(text.split())[:300] or None
    await _save(session, tg, note=note)
    await _ask_payment(session, restaurant, chat_id, tg)


async def _ask_payment(session, restaurant, chat_id, tg) -> None:
    await _save(session, tg, step="payment")
    rows = [[(PAYMENT_LABELS["CASH"], "pay:CASH")]]
    if restaurant.payment_card_number:
        rows.append([(PAYMENT_LABELS["CARD_TRANSFER"], "pay:CARD_TRANSFER")])
    if settings.payme_merchant_id:
        rows.append([(PAYMENT_LABELS["PAYME"], "pay:PAYME")])
    rows.append([("❌ Bekor qilish", "ckcancel")])
    await _say(restaurant, chat_id, "💳 To'lov usulini tanlang:", _kb(rows))


async def _got_payment(session, restaurant, chat_id, tg, method: str) -> None:
    if method not in PAYMENT_LABELS:
        return
    if method == "CARD_TRANSFER" and not restaurant.payment_card_number:
        return
    await _save(session, tg, payment_method=method, step="confirm")
    await _show_summary(session, restaurant, chat_id, tg)


async def _show_summary(session, restaurant, chat_id, tg) -> None:
    state = _state(tg)
    lines, total = _cart_summary(state.get("cart", []))
    parts = [f"🧾 <b>Buyurtmangiz</b>\n\n{_esc(lines)}\n\n<b>Jami: {_esc(_money(total, restaurant.currency))}</b>"]
    parts.append(f"\n👤 {_esc(state.get('name', ''))}\n📱 {_esc(state.get('phone', ''))}")
    if state.get("delivery_type") == "DELIVERY":
        parts.append(f"🚚 Yetkazib berish\n📍 {_esc(state.get('address') or 'Joylashuv yuborilgan')}")
        if state.get("note"):
            parts.append(f"🏢 {_esc(state['note'])}")
    else:
        parts.append("🏃 Olib ketish")
    parts.append(f"💳 {_esc(PAYMENT_LABELS.get(state.get('payment_method', ''), ''))}")
    await _say(
        restaurant, chat_id, "\n".join(parts),
        _kb([[("✅ Tasdiqlash", "confirm")], [("✏️ Ma'lumotlarni o'zgartirish", "ckedit")], [("❌ Bekor qilish", "ckcancel")]]),
        html_mode=True,
    )


async def _confirm_order(session, restaurant, chat_id, tg, idempotency_key: str | None) -> str | None:
    state = _state(tg)
    cart = state.get("cart", [])
    required = ("name", "phone", "delivery_type", "payment_method")
    if not cart or not tg.branch_id or any(not state.get(k) for k in required):
        return "Buyurtma to'liq emas."
    if state["delivery_type"] == "DELIVERY" and not state.get("address"):
        return "Manzil kiritilmagan."
    if (state.get("last_order") or {}).get("checkout_id") == state.get("checkout_id"):
        return "Bu buyurtma allaqachon qabul qilingan."

    try:
        await ensure_can_write(session, restaurant.id)
    except PaymentRequiredError:
        return "Hozircha buyurtma qabul qilinmaydi. Iltimos, keyinroq urinib ko'ring."

    customer = await customers_service.find_or_create(session, restaurant.id, telegram_user_id=chat_id)
    order = await order_service.create_order(
        session,
        restaurant.id,
        None,
        OrderCreate(
            branch_id=tg.branch_id,
            table_id=None,
            source="TELEGRAM",
            items=[OrderItemIn(product_id=uuid.UUID(i["product_id"]), quantity=i["quantity"]) for i in cart],
            customer_name=state["name"],
            customer_phone=state["phone"],
            delivery_type=state["delivery_type"],
            delivery_address=state.get("address") if state["delivery_type"] == "DELIVERY" else None,
            delivery_lat=state.get("lat") if state["delivery_type"] == "DELIVERY" else None,
            delivery_lng=state.get("lng") if state["delivery_type"] == "DELIVERY" else None,
            delivery_note=state.get("note"),
            payment_method=state["payment_method"],
        ),
        idempotency_key=idempotency_key or f"tg-{chat_id}-{state.get('checkout_id')}",
        customer_id=customer.id,
    )
    method = state["payment_method"]
    await _save(
        session, tg, cart=[], step=("proof" if method == "CARD_TRANSFER" else None),
        last_order={"id": str(order.id), "checkout_id": state.get("checkout_id"), "method": method, "number": order.order_number},
    )

    text = f"✅ <b>Buyurtma qabul qilindi!</b>\n№ <b>{order.order_number}</b>\nJami: {_esc(_money(order.total, order.currency))}"
    if state["delivery_type"] == "DELIVERY":
        text += "\n\n👨‍🍳 Buyurtmangiz tayyorlanmoqda. Tayyor bo'lib yo'lga chiqqanda xabar beramiz."
    else:
        text += "\n\n👨‍🍳 Buyurtmangiz tayyorlanmoqda. Tayyor bo'lganda xabar beramiz."
    if method == "CARD_TRANSFER":
        holder = f"\n👤 {_esc(restaurant.payment_card_holder)}" if restaurant.payment_card_holder else ""
        text += (
            f"\n\n💳 <b>To'lov uchun karta:</b>\n<code>{_esc(restaurant.payment_card_number)}</code>{holder}\n"
            f"Summa: <b>{_esc(_money(order.total, order.currency))}</b>\n\n"
            "To'lovni amalga oshirib, <b>chek (skrinshot)ni shu yerga rasm qilib yuboring</b>."
        )
    elif method == "CASH":
        text += "\n\n💵 To'lov: naqd pul."
    await _say(restaurant, chat_id, text, MAIN_KEYBOARD, html_mode=True)

    if method == "PAYME":
        # The order stays unpaid until Payme itself confirms the transaction
        # (its webhook records the Payment) — this link only starts checkout.
        try:
            url = await payme_payments.payme_checkout(session, restaurant.id, order.id, order.total)
            await _say(restaurant, chat_id, "To'lov uchun havola:", {"inline_keyboard": [[{"text": "🟦 Payme orqali to'lash", "url": url}]]})
        except Exception:  # noqa: BLE001
            logger.exception("payme checkout link failed for order %s", order.id)
            await _say(restaurant, chat_id, "To'lov havolasini yaratib bo'lmadi. Operator siz bilan bog'lanadi.")
    return None


# ---------------------------------------------------------------------------
# Payment receipt (photo) from the customer
# ---------------------------------------------------------------------------
async def _got_photo(session, restaurant, chat_id, tg, message: dict) -> None:
    last = _state(tg).get("last_order") or {}
    if not last or last.get("method") != "CARD_TRANSFER" or last.get("proof_saved"):
        await _say(restaurant, chat_id, "Rasm qabul qilinmadi. Chekni buyurtma bergandan keyin yuboring.", MAIN_KEYBOARD)
        return

    photos = message.get("photo") or []
    file_id = photos[-1]["file_id"] if photos else (message.get("document") or {}).get("file_id")
    if not file_id:
        return
    token = restaurant.telegram_bot_token
    try:
        file_path = await telegram_api.get_file_path(token, file_id)
        data = await telegram_api.download_file(token, file_path)
        url = await storage.save(data, f"proof_{uuid.uuid4().hex}.jpg")
    except Exception:  # noqa: BLE001
        logger.exception("could not store payment proof")
        await _say(restaurant, chat_id, "Chekni qabul qilib bo'lmadi. Iltimos, qayta yuboring.")
        return

    order = await order_service.attach_payment_proof(session, restaurant.id, uuid.UUID(last["id"]), url)
    await _save(session, tg, step=None, last_order={**last, "proof_saved": True})
    await _say(restaurant, chat_id, "✅ Chek qabul qilindi. Operator to'lovni tekshiradi, rahmat!", MAIN_KEYBOARD)

    from app.services import notifications as notifications_service

    await notifications_service.create_notification(
        session, restaurant.id, order.branch_id, "PAYMENT",
        title=f"To'lov cheki keldi — #{order.order_number}",
        body=f"{order.customer_name or ''} {order.customer_phone or ''} · {order.total} {order.currency}".strip(),
        link="/dashboard/orders",
    )
