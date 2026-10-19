"""SYNORA platform-owner console: every restaurant's subscription and the
card-transfer payments waiting for approval.

Not tenant-scoped on purpose — it is the one place that sees all restaurants,
so every route requires `User.is_platform_admin` (set only through the CLI,
never through any API).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.core.plans import access_state
from app.database.session import get_db
from app.models.restaurant import Restaurant
from app.models.subscription import SubscriptionPayment
from app.models.user import User
from app.schemas.subscription import (
    OverrideIn,
    PlatformPaymentOut,
    PlatformRestaurantOut,
    RejectIn,
)
from app.services import subscription as subscription_service

router = APIRouter(prefix="/platform", tags=["platform"])


def _restaurant_row(r: Restaurant) -> PlatformRestaurantOut:
    state = access_state(r)
    return PlatformRestaurantOut(
        id=r.id,
        name=r.name,
        slug=r.slug,
        plan=r.plan,
        effective_plan=state.plan,
        status=state.status,
        access=state.access,
        ends_at=state.ends_at,
        days_left=state.days_left,
        created_at=r.created_at,
    )


async def _payment_row(db: AsyncSession, payment: SubscriptionPayment) -> PlatformPaymentOut:
    restaurant = await db.get(Restaurant, payment.restaurant_id)
    base = {c: getattr(payment, c) for c in PlatformPaymentOut.model_fields if c != "restaurant_name"}
    return PlatformPaymentOut(**base, restaurant_name=restaurant.name if restaurant else "")


@router.get("/restaurants", response_model=list[PlatformRestaurantOut])
async def list_restaurants(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_platform_admin),
):
    rows = (await db.scalars(select(Restaurant).order_by(Restaurant.created_at.desc()))).all()
    return [_restaurant_row(r) for r in rows]


@router.get("/payments", response_model=list[PlatformPaymentOut])
async def list_payments(
    status: str | None = Query(default=None, pattern="^(PENDING|APPROVED|REJECTED)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_platform_admin),
):
    stmt = select(SubscriptionPayment).order_by(SubscriptionPayment.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(SubscriptionPayment.status == status)
    return [await _payment_row(db, p) for p in (await db.scalars(stmt)).all()]


@router.post("/payments/{payment_id}/approve", response_model=PlatformPaymentOut)
async def approve_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    payment = await subscription_service.approve_payment(db, admin.id, payment_id)
    return await _payment_row(db, payment)


@router.post("/payments/{payment_id}/reject", response_model=PlatformPaymentOut)
async def reject_payment(
    payment_id: uuid.UUID,
    payload: RejectIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    payment = await subscription_service.reject_payment(db, admin.id, payment_id, payload.reason)
    return await _payment_row(db, payment)


@router.patch("/restaurants/{restaurant_id}/subscription", response_model=PlatformRestaurantOut)
async def override_subscription(
    restaurant_id: uuid.UUID,
    payload: OverrideIn,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    restaurant = await subscription_service.override_subscription(
        db, admin.id, restaurant_id,
        plan=payload.plan, status=payload.status,
        period_end=payload.period_end, clear_period_end=payload.clear_period_end,
    )
    return _restaurant_row(restaurant)
