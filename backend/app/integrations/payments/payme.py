"""Payme (Paycom) Merchant API implementation (Uzbekistan market, Phase M).

Protocol (from Payme's published spec — developer.help.paycom.uz):
  + JSON-RPC 2.0 style POST to the webhook endpoint; responses ALWAYS carry
    HTTP 200, including RPC errors.
  + Authentication: HTTP Basic — login is the merchant login (usually
    "Paycom"), password is the merchant KEY (or TEST KEY for the sandbox).
    Invalid credentials -> RPC error -32504.
  + Amounts are in TIYIN (1 UZS = 100 tiyin). Timestamps are unix MILLISECONDS.
  + Methods: CheckPerformTransaction, CreateTransaction, PerformTransaction,
    CancelTransaction, CheckTransaction, GetStatement.
  + Payme transaction ids are 24-char hex strings; every method must be
    idempotent and return the same answer on replay.
  + States: 1=created, 2=completed, -1=cancelled, -2=cancelled after timeout.
  + Errors: -32700 parse, -32601 no method, -32602 bad params, -32504 auth,
    -32400 internal, -31001 incorrect amount, -31003 transaction not found,
    -31007 cannot cancel (fulfilled), -31008 operation impossible,
    -31050..-31099 account errors (localized message required).
"""

from __future__ import annotations

import base64
import hmac
import time
import uuid
from decimal import Decimal

from app.core.config import settings
from app.integrations.payments.base import (
    ProviderEvent,
    PaymentProvider,
    WebhookUnauthorized,
    register_provider,
)


def tiyin_to_decimal(tiyin: int) -> Decimal:
    return (Decimal(tiyin) / Decimal(100)).quantize(Decimal("0.01"))


def decimal_to_tiyin(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


class PaymeError(Exception):
    """RPC-level error Payme expects back (HTTP still 200)."""

    def __init__(self, code: int, message, data=None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(str(message))


def _localized(uz: str, ru: str, en: str) -> dict:
    return {"uz": uz, "ru": ru, "en": en}


ERR_ORDER_NOT_FOUND = PaymeError(
    -31050, _localized("Buyurtma topilmadi", "Заказ не найден", "Order not found"), "order_id"
)
ERR_OPERATION = PaymeError(
    -31008, _localized("Amaliyotni bajarib bo‘lmadi", "Невозможно выполнить операцию", "Unable to perform operation")
)
ERR_AMOUNT = PaymeError(
    -31001, _localized("Noto‘g‘ri summa", "Неверная сумма", "Incorrect amount")
)
ERR_TXN_NOT_FOUND = PaymeError(
    -31003, _localized("Tranzaksiya topilmadi", "Транзакция не найдена", "Transaction not found")
)
ERR_CANNOT_CANCEL = PaymeError(
    -31007, _localized("Buyurtma bajarilgan", "Заказ выполнен", "Order fulfilled"), "order"
)


def rpc_result(id, result) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def rpc_error(id, error: PaymeError) -> dict:
    body = {"jsonrpc": "2.0", "id": id, "error": {"code": error.code, "message": error.message}}
    if error.data is not None:
        body["error"]["data"] = error.data
    return body


def rpc_parse_error(id) -> dict:
    return rpc_error(id, PaymeError(-32700, "Parse error"))


def rpc_internal_error(id) -> dict:
    return rpc_error(id, PaymeError(-32400, "Internal error"))


@register_provider
class PaymeProvider(PaymentProvider):
    """Merchant-API wiring: checkout link + webhook authentication."""

    name = "PAYME"

    def create_checkout(self, order_id: uuid.UUID, amount: Decimal) -> str:
        merchant_id = settings.payme_merchant_id or settings.payme_login or "test"
        return checkout_url_for(merchant_id, order_id, amount)

    def verify_webhook(self, payload: dict, signature: str | None, raw: str) -> ProviderEvent:
        if not self._authorized(signature):
            raise WebhookUnauthorized()
        if not isinstance(payload, dict) or "params" not in payload or not isinstance(payload["params"], dict):
            raise PaymeError(-32602, "Invalid params")
        params = payload["params"]
        account = params.get("account") or {}
        order_id = None
        raw_order = account.get("order_id")
        if raw_order:
            try:
                order_id = uuid.UUID(str(raw_order))
            except ValueError:
                order_id = None
        return ProviderEvent(
            method=payload.get("method", ""),
            params={k: v for k, v in params.items() if k != "account"},
            order_id=order_id,
            transaction_id=params.get("id"),
            raw=raw,
        )

    def _authorized(self, authorization: str | None) -> bool:
        if not authorization:
            return False
        try:
            scheme, _, encoded = authorization.partition(" ")
            if scheme.lower() != "basic" or not encoded:
                return False
            decoded = base64.b64decode(encoded).decode("utf-8")
            user, _, password = decoded.partition(":")
        except Exception:
            return False
        expected_user = settings.payme_login or "Paycom"
        expected_pass = settings.payme_key
        if not expected_pass:
            return False
        # Constant-time comparison for both halves.
        return (
            hmac.compare_digest(user, expected_user)
            and hmac.compare_digest(password, expected_pass)
        )


def checkout_url_for(merchant_id: str, order_id: uuid.UUID, amount: Decimal) -> str:
    """Direct, test-friendly checkout URL builder (the standard Payme pay link)."""
    base = settings.payme_checkout_base_url.rstrip("/")
    tiyin = decimal_to_tiyin(amount)
    return f"{base}/{merchant_id}/{tiyin}?account[order_id]={order_id}"


def _now_ms() -> int:
    return int(time.time() * 1000)


# --- RPC response assembly helpers reused by the dispatch service -------------
def created_result(transaction_ref: str) -> dict:
    return {"create_time": _now_ms(), "transaction": str(transaction_ref), "state": 1}


def performed_result(transaction_ref: str) -> dict:
    return {"perform_time": _now_ms(), "transaction": str(transaction_ref), "state": 2}


def cancelled_result(transaction_ref: str, reason: int) -> dict:
    state = -2 if int(reason) == 2 else -1
    return {"cancel_time": _now_ms(), "transaction": str(transaction_ref), "state": state}


def checked_result(transaction_ref: str, state: int) -> dict:
    return {"transaction": str(transaction_ref), "state": state}


def get_statement_result(rows) -> dict:
    items = []
    for p in rows:
        items.append({
            "id": p.provider_transaction_id,
            "time": "",
            "amount": decimal_to_tiyin(p.amount),
            "account": {"order_id": str(p.order_id)},
            "create_time": int(p.created_at.timestamp() * 1000) if p.created_at else 0,
            "perform_time": 0,
            "cancel_time": 0,
            "transaction": str(p.order_id),
            "state": 2 if p.status == "PAID" else 1 if p.status == "PENDING" else -1,
            "reason": None,
        })
    return {"transactions": items}