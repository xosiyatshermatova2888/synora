import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionOut(BaseModel):
    plan: str  # effective plan (a trial shows PRO)
    status: str  # TRIAL | ACTIVE
    access: str  # FULL | GRACE | READ_ONLY
    can_write: bool
    ends_at: datetime | None
    days_left: int | None
    grace_days_left: int | None
    billing_cycle: str | None
    branch_count: int
    branch_limit: int | None
    features: list[str]


class PlanInfo(BaseModel):
    plan: str
    monthly_price: int | None  # None = contact sales
    annual_price: int | None
    branch_limit: int | None
    features: list[str]


class PlansOut(BaseModel):
    plans: list[PlanInfo]
    currency: str
    payment_card: str
    payment_holder: str
    trial_days: int
    grace_days: int


class PaymentRequestIn(BaseModel):
    plan: str = Field(min_length=1, max_length=20)
    billing_cycle: str = Field(pattern="^(MONTHLY|ANNUAL)$")


class ReceiptIn(BaseModel):
    receipt_url: str = Field(min_length=1, max_length=500)


class SubscriptionPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    restaurant_id: uuid.UUID
    plan: str
    billing_cycle: str
    amount: Decimal
    currency: str
    status: str
    receipt_url: str | None
    note: str | None
    reviewed_at: datetime | None
    period_start: datetime | None
    period_end: datetime | None
    created_at: datetime


# --- Platform (SYNORA staff) ----------------------------------------------------


class PlatformPaymentOut(SubscriptionPaymentOut):
    restaurant_name: str


class PlatformRestaurantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str  # stored plan
    effective_plan: str
    status: str
    access: str
    ends_at: datetime | None
    days_left: int | None
    created_at: datetime


class RejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class OverrideIn(BaseModel):
    plan: str | None = None
    status: str | None = None
    period_end: datetime | None = None
    clear_period_end: bool = False
