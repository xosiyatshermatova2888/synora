"""A restaurant's own subscription: current plan/usage, the plan catalog, and
the card-transfer payment requests it files for the SYNORA owner to approve.

Payments/catalog are owner/admin only (`users.manage`). Stays writable after the subscription
lapses (see `_WRITABLE_WHEN_EXPIRED` in deps.py) so a restaurant can always pay
its way back in.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user_restaurant, require_permission
from app.core.config import settings
from app.core.plans import (
    BRANCH_LIMIT,
    MONTHLY_PRICE,
    PLANS,
    GRACE_DAYS,
    TRIAL_DAYS,
    features_of,
    price_for,
)
from app.database.session import get_db
from app.models.user import User
from app.schemas.subscription import (
    PaymentRequestIn,
    PlanInfo,
    PlansOut,
    ReceiptIn,
    SubscriptionOut,
    SubscriptionPaymentOut,
)
from app.services import subscription as subscription_service

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionOut)
async def get_subscription(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Open to every staff role: the UI needs the plan to lock/unlock modules,
    # and nothing here is sensitive. Paying/requesting stays owner/admin only.
    state = await subscription_service.get_access(db, current_tenant)
    restaurant = await subscription_service.load_restaurant(db, current_tenant)
    return SubscriptionOut(
        plan=state.plan,
        status=state.status,
        access=state.access,
        can_write=state.can_write,
        ends_at=state.ends_at,
        days_left=state.days_left,
        grace_days_left=state.grace_days_left,
        billing_cycle=restaurant.billing_cycle,
        branch_count=await subscription_service.branch_count(db, current_tenant),
        branch_limit=BRANCH_LIMIT[state.plan],
        features=features_of(state.plan),
    )


@router.get("/plans", response_model=PlansOut)
async def get_plans(
    _tenant: uuid.UUID = Depends(get_current_tenant),
    _: None = Depends(require_permission("users.manage")),
):
    plans = [
        PlanInfo(
            plan=name,
            monthly_price=MONTHLY_PRICE.get(name),
            annual_price=price_for(name, "ANNUAL") if name in MONTHLY_PRICE else None,
            branch_limit=BRANCH_LIMIT[name],
            features=features_of(name),
        )
        for name in PLANS
    ]
    return PlansOut(
        plans=plans,
        currency="UZS",
        payment_card=settings.synora_payment_card,
        payment_holder=settings.synora_payment_holder,
        trial_days=TRIAL_DAYS,
        grace_days=GRACE_DAYS,
    )


@router.get("/payments", response_model=list[SubscriptionPaymentOut])
async def list_payments(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await subscription_service.list_payments(db, current_tenant)


@router.post("/payments", response_model=SubscriptionPaymentOut, status_code=201)
async def request_payment(
    payload: PaymentRequestIn,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await subscription_service.request_payment(
        db, current_tenant, current_user.id, payload.plan, payload.billing_cycle
    )


@router.post("/payments/{payment_id}/receipt", response_model=SubscriptionPaymentOut)
async def attach_receipt(
    payment_id: uuid.UUID,
    payload: ReceiptIn,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    return await subscription_service.attach_receipt(
        db, current_tenant, current_user.id, payment_id, payload.receipt_url
    )
