"""Payments + cash shift API (Phase H). Multi-payment-ready schema (Section 14);
cash shift close is optimistic-lock-safe (Section 15)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user_restaurant, require_permission
from app.core.config import settings
from app.database.session import get_db
from app.models.payment import CashShift
from app.models.user import User
from app.repositories.payments import CashShiftRepository, PaymentRepository
from app.schemas.payments import (
    CashShiftClose,
    CashShiftOpen,
    CashShiftOut,
    PaymentCheckoutCreate,
    PaymentCreate,
    PaymentOut,
)
from app.services import payments as payment_service
from app.services.payme_payments import handle_payme_webhook, payme_checkout

router = APIRouter(tags=["payments"])


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
@router.post("/payments", response_model=PaymentOut, status_code=201)
async def add_payment(
    payload: PaymentCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("payments.create")),
):
    payment = await payment_service.add_payment(
        db,
        current_tenant,
        current_user.id,
        payload.order_id,
        payload.amount,
        payload.method,
        payload.reference,
    )
    await db.refresh(payment)
    return payment


@router.get("/orders/{order_id}/payments", response_model=list[PaymentOut])
async def list_order_payments(
    order_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.read")),
):
    return await PaymentRepository(db).list_for_order(current_tenant, order_id)


# ---------------------------------------------------------------------------
# Payment gateways (Phase M)
# ---------------------------------------------------------------------------
@router.post("/payments/{order_id}/payme-checkout", response_model=dict)
async def create_payme_checkout(
    order_id: uuid.UUID,
    payload: PaymentCheckoutCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.manage")),
):
    url = await payme_checkout(db, current_tenant, order_id, payload.amount)
    return {"checkout_url": url}


@router.post("/payments/webhooks/payme")
async def payme_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Payme Merchant API: HTTP 200 ALWAYS (errors ride inside the RPC envelope).
    body = (await request.body()).decode("utf-8", errors="replace")
    return await handle_payme_webhook(
        db, body, authorization=request.headers.get("authorization")
    )


# ---------------------------------------------------------------------------
# Cash shifts
# ---------------------------------------------------------------------------
@router.get("/cash-shifts", response_model=list[CashShiftOut])
async def list_cash_shifts(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.read")),
    branch_id: uuid.UUID | None = Query(default=None),
):
    stmt = select(CashShift).where(CashShift.restaurant_id == current_tenant)
    if branch_id is not None:
        stmt = stmt.where(CashShift.branch_id == branch_id)
    return list((await db.scalars(stmt.order_by(CashShift.opened_at.desc()))).all())


@router.post("/cash-shifts/open", response_model=CashShiftOut, status_code=201)
async def open_cash_shift(
    payload: CashShiftOpen,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.manage")),
):
    return await payment_service.open_shift(
        db,
        current_tenant,
        payload.branch_id,
        current_user.id,
        payload.opening_balance,
    )


@router.post("/cash-shifts/{shift_id}/close", response_model=CashShiftOut)
async def close_cash_shift(
    shift_id: uuid.UUID,
    payload: CashShiftClose,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.manage")),
):
    return await payment_service.close_shift(
        db,
        current_tenant,
        shift_id,
        payload.actual_closing_balance,
        payload.version,
    )