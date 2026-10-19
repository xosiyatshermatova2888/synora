"""Subscription logic: the cached per-restaurant access gate, feature/branch
limits, and the payment-request → approval flow.

Two layers of enforcement, both server-side (the UI only mirrors them):
  * `get_current_tenant` calls `ensure_can_write` — once the grace period is
    over every non-GET request is refused with 402 `subscription_expired`.
  * `require_feature` / `ensure_branch_capacity` — plan limits, 402
    `plan_upgrade_required`.
"""

from __future__ import annotations

import calendar
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import (
    BRANCH_LIMIT,
    MONTHLY_PRICE,
    PLANS,
    TRIAL_DAYS,
    AccessState,
    access_state,
    has_feature,
    price_for,
)
from app.models.branch import Branch
from app.models.restaurant import Restaurant
from app.models.subscription import BILLING_CYCLES, SubscriptionPayment
from app.services.audit import log_action
from app.services.notifications import create_notification
from app.utils.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PaymentRequiredError,
    ValidationError,
)

# restaurant_id -> (cached_at_monotonic, AccessState)
_CACHE: dict[uuid.UUID, tuple[float, AccessState]] = {}

PAYABLE_PLANS = tuple(MONTHLY_PRICE)  # ENTERPRISE is sold by contact, not by card


def invalidate_access_cache(restaurant_id: uuid.UUID | None = None) -> None:
    if restaurant_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(restaurant_id, None)


async def load_restaurant(session: AsyncSession, restaurant_id: uuid.UUID) -> Restaurant:
    restaurant = await session.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise NotFoundError(detail="Restaurant not found.")
    return restaurant


async def get_access(session: AsyncSession, restaurant_id: uuid.UUID) -> AccessState:
    ttl = settings.subscription_cache_seconds
    if ttl > 0:
        hit = _CACHE.get(restaurant_id)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
    state = access_state(await load_restaurant(session, restaurant_id))
    if ttl > 0:
        _CACHE[restaurant_id] = (time.monotonic(), state)
    return state


def _expired_error() -> PaymentRequiredError:
    return PaymentRequiredError(
        "subscription_expired",
        "Your subscription has expired. The account is read-only until it is renewed.",
    )


async def ensure_can_write(session: AsyncSession, restaurant_id: uuid.UUID) -> AccessState:
    state = await get_access(session, restaurant_id)
    if not state.can_write:
        raise _expired_error()
    return state


async def require_feature_for(session: AsyncSession, restaurant_id: uuid.UUID, feature: str) -> None:
    state = await get_access(session, restaurant_id)
    if not has_feature(state.plan, feature):
        from app.core.plans import FEATURE_MIN_PLAN

        raise PaymentRequiredError(
            "plan_upgrade_required",
            f"This feature is not included in the {state.plan} plan.",
            feature=feature,
            required_plan=FEATURE_MIN_PLAN[feature],
            current_plan=state.plan,
        )


async def branch_count(session: AsyncSession, restaurant_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Branch).where(Branch.restaurant_id == restaurant_id)
        )
        or 0
    )


async def ensure_branch_capacity(session: AsyncSession, restaurant_id: uuid.UUID) -> None:
    state = await get_access(session, restaurant_id)
    limit = BRANCH_LIMIT[state.plan]
    if limit is not None and await branch_count(session, restaurant_id) >= limit:
        needed = "PRO" if state.plan == "BUSINESS" else "ENTERPRISE"
        raise PaymentRequiredError(
            "plan_upgrade_required",
            f"The {state.plan} plan allows at most {limit} branch(es).",
            feature="multi_branch",
            required_plan=needed,
            current_plan=state.plan,
            branch_limit=limit,
        )


def start_trial(restaurant: Restaurant, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    restaurant.plan = "BUSINESS"
    restaurant.subscription_status = "TRIAL"
    restaurant.trial_ends_at = now + timedelta(days=TRIAL_DAYS)
    restaurant.current_period_end = None


# --- Payments -----------------------------------------------------------------


async def request_payment(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
    cycle: str,
) -> SubscriptionPayment:
    if plan not in PAYABLE_PLANS:
        raise ValidationError(detail="This plan cannot be paid by card; contact SYNORA.")
    if cycle not in BILLING_CYCLES:
        raise ValidationError(detail="Billing cycle must be MONTHLY or ANNUAL.")

    # One open request at a time keeps the owner's review queue unambiguous.
    pending = await session.scalar(
        select(SubscriptionPayment).where(
            SubscriptionPayment.restaurant_id == restaurant_id,
            SubscriptionPayment.status == "PENDING",
        )
    )
    if pending is not None:
        raise ConflictError(detail="You already have a payment waiting for review.")

    payment = SubscriptionPayment(
        restaurant_id=restaurant_id,
        plan=plan,
        billing_cycle=cycle,
        amount=Decimal(price_for(plan, cycle)),
        currency="UZS",
        status="PENDING",
        requested_by_user_id=user_id,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    await log_action(
        session, restaurant_id, user_id, "subscription.payment_requested",
        "subscription_payment", payment.id, f"{plan} {cycle} {payment.amount}",
    )
    return payment


async def get_payment(session: AsyncSession, payment_id: uuid.UUID, restaurant_id: uuid.UUID | None) -> SubscriptionPayment:
    stmt = select(SubscriptionPayment).where(SubscriptionPayment.id == payment_id)
    if restaurant_id is not None:  # tenant scope; platform admins pass None
        stmt = stmt.where(SubscriptionPayment.restaurant_id == restaurant_id)
    payment = await session.scalar(stmt)
    if payment is None:
        raise NotFoundError(detail="Payment not found.")
    return payment


def _is_own_upload(url: str) -> bool:
    """Receipts must be files we stored ourselves. The platform admin opens this
    link, so a `javascript:` or foreign URL here would be a stored-XSS /
    phishing vector against the one account that can see every tenant."""
    if url.startswith(("/uploads/", "/files/")) and ".." not in url and "//" not in url[1:]:
        return True
    bases = [b.rstrip("/") for b in (settings.s3_public_url_base, settings.s3_endpoint) if b.startswith("http")]
    return any(url.startswith(base + "/") for base in bases)


async def attach_receipt(
    session: AsyncSession, restaurant_id: uuid.UUID, user_id: uuid.UUID, payment_id: uuid.UUID, receipt_url: str
) -> SubscriptionPayment:
    if not _is_own_upload(receipt_url):
        raise ValidationError(detail="The receipt must be an image uploaded through SYNORA.")
    payment = await get_payment(session, payment_id, restaurant_id)
    if payment.status != "PENDING":
        raise BusinessRuleError(detail="Only a pending payment can take a receipt.")
    payment.receipt_url = receipt_url
    await session.commit()
    await session.refresh(payment)
    await log_action(
        session, restaurant_id, user_id, "subscription.receipt_uploaded",
        "subscription_payment", payment.id, "receipt uploaded",
    )
    return payment


async def list_payments(session: AsyncSession, restaurant_id: uuid.UUID) -> list[SubscriptionPayment]:
    return list(
        (
            await session.scalars(
                select(SubscriptionPayment)
                .where(SubscriptionPayment.restaurant_id == restaurant_id)
                .order_by(SubscriptionPayment.created_at.desc())
            )
        ).all()
    )


def _add_months(moment: datetime, months: int) -> datetime:
    index = moment.month - 1 + months
    year, month = moment.year + index // 12, index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])  # Jan 31 + 1 month = Feb 28
    return moment.replace(year=year, month=month, day=day)


def _add_period(start: datetime, cycle: str) -> datetime:
    return _add_months(start, 12 if cycle == "ANNUAL" else 1)


async def approve_payment(
    session: AsyncSession, admin_id: uuid.UUID, payment_id: uuid.UUID
) -> SubscriptionPayment:
    """Activate the paid plan. Idempotent: approving twice never extends twice."""
    payment = await get_payment(session, payment_id, None)
    if payment.status == "APPROVED":
        return payment
    if payment.status == "REJECTED":
        raise BusinessRuleError(detail="A rejected payment cannot be approved; ask for a new request.")

    restaurant = await load_restaurant(session, payment.restaurant_id)
    now = datetime.now(timezone.utc)
    # Renewing early adds on top of the remaining time; renewing late starts now.
    current_end = restaurant.current_period_end
    if current_end is not None and current_end.tzinfo is None:
        current_end = current_end.replace(tzinfo=timezone.utc)
    same_plan_active = (
        restaurant.subscription_status == "ACTIVE"
        and restaurant.plan == payment.plan
        and current_end is not None
        and current_end > now
    )
    start = current_end if same_plan_active else now
    payment.period_start = start
    payment.period_end = _add_period(start, payment.billing_cycle)

    restaurant.plan = payment.plan
    restaurant.subscription_status = "ACTIVE"
    restaurant.billing_cycle = payment.billing_cycle
    restaurant.current_period_end = payment.period_end
    restaurant.trial_ends_at = None

    payment.status = "APPROVED"
    payment.reviewed_by_user_id = admin_id
    payment.reviewed_at = now
    await session.commit()
    invalidate_access_cache(restaurant.id)
    await log_action(
        session, restaurant.id, admin_id, "subscription.payment_approved",
        "subscription_payment", payment.id,
        f"{payment.plan} {payment.billing_cycle} until {payment.period_end:%Y-%m-%d}",
    )
    await create_notification(
        session, restaurant.id, None, "SUBSCRIPTION",
        "Obuna faollashtirildi",
        f"{payment.plan} tarifi {payment.period_end:%d.%m.%Y} gacha faol.",
        "/dashboard/subscription",
    )
    await session.refresh(payment)
    return payment


async def reject_payment(
    session: AsyncSession, admin_id: uuid.UUID, payment_id: uuid.UUID, reason: str | None
) -> SubscriptionPayment:
    payment = await get_payment(session, payment_id, None)
    if payment.status != "PENDING":
        raise BusinessRuleError(detail="Only a pending payment can be rejected.")
    payment.status = "REJECTED"
    payment.note = reason
    payment.reviewed_by_user_id = admin_id
    payment.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
    await log_action(
        session, payment.restaurant_id, admin_id, "subscription.payment_rejected",
        "subscription_payment", payment.id, reason or "rejected",
    )
    await create_notification(
        session, payment.restaurant_id, None, "SUBSCRIPTION",
        "To'lov rad etildi", reason or "Chek tasdiqlanmadi.", "/dashboard/subscription",
    )
    await session.refresh(payment)
    return payment


async def override_subscription(
    session: AsyncSession,
    admin_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    *,
    plan: str | None,
    status: str | None,
    period_end: datetime | None,
    clear_period_end: bool,
) -> Restaurant:
    """Platform-owner escape hatch: gift a plan, extend a trial, fix a mistake."""
    restaurant = await load_restaurant(session, restaurant_id)
    if plan is not None:
        if plan not in PLANS:
            raise ValidationError(detail="Unknown plan.")
        restaurant.plan = plan
    if status is not None:
        if status not in ("TRIAL", "ACTIVE"):
            raise ValidationError(detail="Status must be TRIAL or ACTIVE.")
        restaurant.subscription_status = status
    if clear_period_end:
        restaurant.current_period_end = None
        restaurant.trial_ends_at = None
    elif period_end is not None:
        if restaurant.subscription_status == "TRIAL":
            restaurant.trial_ends_at = period_end
        else:
            restaurant.current_period_end = period_end
    await session.commit()
    invalidate_access_cache(restaurant.id)
    await session.refresh(restaurant)
    await log_action(
        session, restaurant.id, admin_id, "subscription.override", "restaurant", restaurant.id,
        f"plan={plan} status={status} end={period_end.isoformat() if period_end else None} clear={clear_period_end}",
    )
    return restaurant
