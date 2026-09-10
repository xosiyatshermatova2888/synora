"""Payme Merchant-API webhook dispatch (Phase M).

This is the server side of the Payme protocol (JSON-RPC over POST, always HTTP
200, Basic-auth verified). Every "method" maps to an idempotent handler:

  CheckPerformTransaction  -> pre-flight: is this order payable for this amount?
  CreateTransaction        -> record PENDING payment (provider-txn unique ~
                              webhook retry idempotency)
  PerformTransaction       -> money captured: mark PAID, settle the order
  CancelTransaction        -> mark VOID (never retro-cancels a fulfilled order)
  CheckTransaction / GetStatement -> reconciliation helpers

Amounts arrive in tiyin and are validated against the order's outstanding
balance so the webhook can never over-collect or pay a non-open order.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.payments.base import get_provider, WebhookUnauthorized
from app.integrations.payments.payme import (
    ERR_AMOUNT,
    ERR_CANNOT_CANCEL,
    ERR_OPERATION,
    ERR_ORDER_NOT_FOUND,
    ERR_TXN_NOT_FOUND,
    PaymeError,
    cancelled_result,
    checked_result,
    created_result,
    decimal_to_tiyin,
    get_statement_result,
    performed_result,
    rpc_error,
    rpc_internal_error,
    rpc_parse_error,
    rpc_result,
    tiyin_to_decimal,
)
from app.models.order import Order
from app.models.payment import Payment
from app.services import orders as order_service
from app.services.payments import total_paid
from app.utils.errors import NotFoundError

logger = logging.getLogger("synora.payme")

PROVIDER = "PAYME"
_ACCOUNT_FIELD = "order_id"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
async def _order_or_error(session: AsyncSession, order_id: uuid.UUID | None) -> Order:
    if order_id is None:
        raise PaymeError(ERR_ORDER_NOT_FOUND.code, ERR_ORDER_NOT_FOUND.message, ERR_ORDER_NOT_FOUND.data)
    order = await session.get(Order, order_id)
    if order is None:
        raise PaymeError(ERR_ORDER_NOT_FOUND.code, ERR_ORDER_NOT_FOUND.message, ERR_ORDER_NOT_FOUND.data)
    return order


async def _find_payment(session: AsyncSession, txn_id: str | None) -> Payment | None:
    if not txn_id:
        return None
    return await session.scalar(
        select(Payment).where(
            Payment.provider == PROVIDER,
            Payment.provider_transaction_id == txn_id,
        )
    )


def _ref(payment: Payment) -> str:
    return str(payment.reference or payment.id)


def _validate_payable(order: Order, amount_tiyin: int) -> Decimal:
    if order.status not in ("OPEN", "PARTIALLY_PAID"):
        raise PaymeError(ERR_OPERATION.code, ERR_OPERATION.message, ERR_OPERATION.data)
    amount = tiyin_to_decimal(amount_tiyin)
    if amount <= 0:
        raise PaymeError(ERR_AMOUNT.code, ERR_AMOUNT.message, ERR_AMOUNT.data)
    return amount


# ---------------------------------------------------------------------------
# RPC handlers
# ---------------------------------------------------------------------------
async def _check_perform(session: AsyncSession, params: dict, order_id: uuid.UUID | None, txn: str | None, rpc_id) -> dict:
    order = await _order_or_error(session, order_id)
    amount = _validate_payable(order, int(params.get("amount", 0)))
    paid = await total_paid(session, order.restaurant_id, order.id)
    remaining = order.total - paid
    if amount > remaining:
        raise PaymeError(ERR_AMOUNT.code, ERR_AMOUNT.message, ERR_AMOUNT.data)
    return rpc_result(rpc_id, {"allow": True})


async def _create_transaction(session: AsyncSession, params: dict, order_id: uuid.UUID | None, txn: str | None, rpc_id) -> dict:
    order = await _order_or_error(session, order_id)
    amount_tiyin = int(params.get("amount", 0))
    amount = _validate_payable(order, amount_tiyin)

    existing = await _find_payment(session, txn)
    if existing is not None:
        if decimal_to_tiyin(existing.amount) != amount_tiyin:
            raise PaymeError(ERR_AMOUNT.code, ERR_AMOUNT.message, ERR_AMOUNT.data)
        if existing.status == "PAID":
            return rpc_result(rpc_id, performed_result(_ref(existing)))
        if existing.status == "VOID":
            return rpc_result(rpc_id, cancelled_result(_ref(existing), int(params.get("reason", 4))))
        return rpc_result(rpc_id, created_result(_ref(existing)))

    paid = await total_paid(session, order.restaurant_id, order.id)
    remaining = order.total - paid
    if amount > remaining:
        raise PaymeError(ERR_AMOUNT.code, ERR_AMOUNT.message, ERR_AMOUNT.data)

    payment = Payment(
        restaurant_id=order.restaurant_id,
        order_id=order.id,
        amount=amount,
        method=PROVIDER,
        status="PENDING",
        reference=str(order.id),
        provider=PROVIDER,
        provider_transaction_id=txn or str(uuid.uuid4()),
        provider_state="1",
        created_by_user_id=None,
    )
    # Unique (provider, provider_transaction_id) makes redelivery idempotent;
    # a racing duplicate insert is rolled back and re-read below.
    savepoint = await session.begin_nested()
    session.add(payment)
    try:
        await savepoint.commit()
    except IntegrityError:
        await savepoint.rollback()
        existing = await _find_payment(session, txn)
        if existing is None:
            raise
        return rpc_result(rpc_id, created_result(_ref(existing)))

    await session.commit()
    return rpc_result(rpc_id, created_result(_ref(payment)))


async def _perform_transaction(session: AsyncSession, params: dict, order_id: uuid.UUID | None, txn: str | None, rpc_id) -> dict:
    payment = await _find_payment(session, txn)
    if payment is None:
        raise PaymeError(ERR_TXN_NOT_FOUND.code, ERR_TXN_NOT_FOUND.message, ERR_TXN_NOT_FOUND.data)
    if payment.status == "PAID":
        return rpc_result(rpc_id, performed_result(_ref(payment)))
    if payment.status == "VOID":
        raise PaymeError(ERR_OPERATION.code, ERR_OPERATION.message, ERR_OPERATION.data)

    order = await _order_or_error(session, payment.order_id)
    _validate_payable(order, decimal_to_tiyin(payment.amount))

    payment.status = "PAID"
    payment.provider_state = "2"
    await session.flush()

    paid = await total_paid(session, order.restaurant_id, order.id)
    if paid >= order.total:
        await order_service.transition_order(session, order.restaurant_id, order.id, "COMPLETED")
    elif order.status != "PARTIALLY_PAID":
        await order_service.transition_order(session, order.restaurant_id, order.id, "PARTIALLY_PAID")

    await session.commit()
    return rpc_result(rpc_id, performed_result(_ref(payment)))


async def _cancel_transaction(session: AsyncSession, params: dict, order_id: uuid.UUID | None, txn: str | None, rpc_id) -> dict:
    payment = await _find_payment(session, txn)
    if payment is None:
        raise PaymeError(ERR_TXN_NOT_FOUND.code, ERR_TXN_NOT_FOUND.message, ERR_TXN_NOT_FOUND.data)
    if payment.status == "PAID":
        raise PaymeError(ERR_CANNOT_CANCEL.code, ERR_CANNOT_CANCEL.message, ERR_CANNOT_CANCEL.data)

    reason = int(params.get("reason", 4))
    payment.status = "VOID"
    payment.provider_state = f"-{reason}"
    await session.commit()
    return rpc_result(rpc_id, cancelled_result(_ref(payment), reason))


async def _check_transaction(session: AsyncSession, params: dict, order_id: uuid.UUID | None, txn: str | None, rpc_id) -> dict:
    payment = await _find_payment(session, txn)
    if payment is None:
        raise PaymeError(ERR_TXN_NOT_FOUND.code, ERR_TXN_NOT_FOUND.message, ERR_TXN_NOT_FOUND.data)
    state = {"PAID": 2, "PENDING": 1, "VOID": -1}[payment.status]
    return rpc_result(rpc_id, checked_result(_ref(payment), state))


async def _get_statement(session: AsyncSession, params: dict, order_id: uuid.UUID | None, txn: str | None, rpc_id) -> dict:
    frm = datetime.fromtimestamp(int(params.get("from", 0)) / 1000)
    to = datetime.fromtimestamp(int(params.get("to", 0)) / 1000)
    rows = (
        await session.scalars(
            select(Payment).where(
                Payment.provider == PROVIDER,
                Payment.created_at >= frm,
                Payment.created_at <= to,
            )
        )
    ).all()
    return rpc_result(rpc_id, get_statement_result(rows))


_HANDLERS: dict[str, Callable] = {
    "CheckPerformTransaction": _check_perform,
    "CreateTransaction": _create_transaction,
    "PerformTransaction": _perform_transaction,
    "CancelTransaction": _cancel_transaction,
    "CheckTransaction": _check_transaction,
    "GetStatement": _get_statement,
}


async def handle_payme_webhook(session: AsyncSession, body_raw: str, authorization: str | None) -> dict:
    """Entry point for POST /api/v1/payments/webhooks/payme. Always HTTP-200-safe."""
    provider = get_provider(PROVIDER)
    try:
        payload = json.loads(body_raw or "")
    except ValueError:
        return rpc_parse_error(0)
    rpc_id = payload.get("id", 0)

    try:
        event = provider.verify_webhook(payload, authorization, body_raw)
    except WebhookUnauthorized:
        logger.warning("payme webhook rejected: bad Authorization header")
        return rpc_error(rpc_id, PaymeError(-32504, "Insufficient privileges"))
    except PaymeError as exc:
        return rpc_error(rpc_id, exc)

    handler = _HANDLERS.get(event.method)
    if handler is None:
        return rpc_error(rpc_id, PaymeError(-32601, "Method not found", event.method))

    try:
        return await handler(session, event.params, event.order_id, event.transaction_id, rpc_id)
    except PaymeError as exc:
        return rpc_error(rpc_id, exc)
    except Exception:
        logger.exception("payme webhook handler failed", extra={"method": event.method})
        return rpc_internal_error(rpc_id)


async def payme_checkout(session: AsyncSession, restaurant_id: uuid.UUID, order_id: uuid.UUID, amount: Decimal) -> str:
    """Build the Payme check-out URL for an open order, or raise if not payable."""
    order = await order_service.get_order(session, restaurant_id, order_id)
    amount = amount.quantize(Decimal("0.01"))
    if order.status not in ("OPEN", "PARTIALLY_PAID"):
        raise NotFoundError(detail="Order is not open for payment.")
    if amount <= 0:
        raise PaymeError(ERR_AMOUNT.code, ERR_AMOUNT.message, ERR_AMOUNT.data)
    paid = await total_paid(session, restaurant_id, order_id)
    if amount > order.total - paid:
        raise NotFoundError(detail="Payment exceeds the outstanding balance.")
    provider = get_provider(PROVIDER)
    url = provider.create_checkout(order.id, amount)
    logger.info("payme checkout generated", extra={"order_id": str(order_id), "amount": str(amount)})
    return url