"""Payments + cash shift schemas. Money is Decimal everywhere (Section 12A)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class PaymentCreate(BaseModel):
    order_id: uuid.UUID
    amount: Decimal = Field(ge=0, decimal_places=2)
    method: str = Field(default="CASH", pattern="^(CASH|CARD|TRANSFER|QR)$")
    reference: str | None = Field(default=None, max_length=100)


class PaymentCheckoutCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    method: str
    status: str
    reference: str | None
    created_at: datetime


class CashShiftOpen(BaseModel):
    branch_id: uuid.UUID
    opening_balance: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class CashShiftClose(BaseModel):
    actual_closing_balance: Decimal = Field(ge=0, decimal_places=2)
    version: int = Field(ge=1)


class CashShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    branch_id: uuid.UUID
    cashier_user_id: uuid.UUID | None
    opened_at: datetime
    closed_at: datetime | None
    opening_balance: Decimal
    expected_closing_balance: Decimal | None
    actual_closing_balance: Decimal | None
    status: str
    version: int