"""Order Engine schemas.

Money is Decimal everywhere (Numeric(12,2); Section 12A). Order creation is
idempotent via the `Idempotency-Key` header (Section 11). Item unit prices are
snapshotted server-side from the current product (Section 13) — clients send
product_id + quantity + modifier_id list, never prices.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class OrderModifierSelection(BaseModel):
    modifier_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)


class OrderItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=1000)
    notes: str | None = None
    modifiers: list[OrderModifierSelection] = []


class OrderCreate(BaseModel):
    branch_id: uuid.UUID
    table_id: uuid.UUID | None = None
    source: str = Field(default="POS", pattern="^(POS|WAITER|QR|TELEGRAM|DELIVERY|ONLINE)$")
    notes: str | None = None
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemModifierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    modifier_name_snapshot: str
    price: Decimal
    quantity: int


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID | None
    product_name_snapshot: str
    unit_price: Decimal
    quantity: int
    discount: Decimal
    notes: str | None
    modifiers: list[OrderItemModifierOut] = []


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    restaurant_id: uuid.UUID
    branch_id: uuid.UUID
    table_id: uuid.UUID | None
    order_number: int
    status: str
    kitchen_status: str
    source: str
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    service_charge: Decimal
    total: Decimal
    currency: str
    notes: str | None
    waiter_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    items: list[OrderItemOut] = []
    created_at: datetime


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(DRAFT|OPEN|COMPLETED|CANCELLED|PARTIALLY_PAID|REFUNDED)$")


class KitchenStatusUpdate(BaseModel):
    kitchen_status: str = Field(pattern="^(NEW|PREPARING|READY|SERVED)$")