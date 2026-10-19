"""Tariff plans: what each plan includes and how a subscription's dates map to
what a restaurant may do right now.

`access_state` is a pure function of (restaurant fields, now) so every rule is
unit-testable; nothing runs on a timer — expiry is evaluated lazily from the
stored dates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

PLANS = ("BUSINESS", "PRO", "AI_PREMIUM", "ENTERPRISE")
_RANK = {name: i for i, name in enumerate(PLANS)}

TRIAL_DAYS = 14
GRACE_DAYS = 7
TRIAL_PLAN = "PRO"  # a trial shows the full product

# Everything not listed here (POS, waiter app, KDS, QR menu, Telegram orders,
# basic reports) is part of every plan.
FEATURE_MIN_PLAN: dict[str, str] = {
    "inventory": "PRO",
    "crm": "PRO",
    "advanced_reports": "PRO",
    "multi_branch": "PRO",
    "ai_assistant": "AI_PREMIUM",
}

BRANCH_LIMIT: dict[str, int | None] = {
    "BUSINESS": 1,
    "PRO": 3,
    "AI_PREMIUM": 3,
    "ENTERPRISE": None,
}

MONTHLY_PRICE: dict[str, int] = {"BUSINESS": 299_000, "PRO": 499_000, "AI_PREMIUM": 799_000}
ANNUAL_MONTHS_CHARGED = 10  # yearly = pay 10 months, get 12


def plan_rank(plan: str) -> int:
    return _RANK[plan]


def has_feature(plan: str, feature: str) -> bool:
    required = FEATURE_MIN_PLAN.get(feature)
    return required is None or plan_rank(plan) >= plan_rank(required)


def features_of(plan: str) -> list[str]:
    return [f for f in FEATURE_MIN_PLAN if has_feature(plan, f)]


def price_for(plan: str, cycle: str) -> int:
    monthly = MONTHLY_PRICE[plan]
    return monthly * ANNUAL_MONTHS_CHARGED if cycle == "ANNUAL" else monthly


@dataclass(frozen=True)
class AccessState:
    plan: str  # effective plan (TRIAL shows PRO)
    status: str  # TRIAL | ACTIVE
    access: str  # FULL | GRACE | READ_ONLY
    ends_at: datetime | None
    days_left: int | None  # whole days until ends_at (rounded up); negative = whole days since
    grace_days_left: int | None  # only while access == GRACE

    @property
    def can_write(self) -> bool:
        return self.access != "READ_ONLY"


def _aware(moment: datetime | None) -> datetime | None:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def access_state(restaurant, now: datetime | None = None) -> AccessState:
    now = now or datetime.now(timezone.utc)
    status = restaurant.subscription_status or "ACTIVE"
    if status == "TRIAL":
        plan, ends_at = TRIAL_PLAN, _aware(restaurant.trial_ends_at)
    else:
        plan, ends_at = restaurant.plan or "BUSINESS", _aware(restaurant.current_period_end)

    if ends_at is None:
        return AccessState(plan, status, "FULL", None, None, None)

    if now <= ends_at:
        # Round up so "23 h left" reads as 1 day, never 0, while access is full.
        return AccessState(plan, status, "FULL", ends_at, (ends_at - now).days + 1, None)
    days_past = (now - ends_at).days  # whole days since it ended
    grace_end = ends_at + timedelta(days=GRACE_DAYS)
    if now <= grace_end:
        return AccessState(plan, status, "GRACE", ends_at, -days_past, (grace_end - now).days + 1)
    return AccessState(plan, status, "READ_ONLY", ends_at, -days_past, None)
