"""Order Engine schemas.

Money is Decimal everywhere (Numeric(12,2); Section 12A). Order creation is
idempotent via the `Idempotency-Key` header (Section 11). Item unit prices are
snapshotted server-side from the current product (Section 13) — clients send
product_id + quantity + modifier_id list, never prices.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator


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
    # `discount` is a currency amount when discount_type=FIXED, or a 0-100
    # percentage when discount_type=PERCENT; resolved to a currency amount
    # server-side by `app/services/pricing.py::resolve_discount`.
    discount_type: Literal["FIXED", "PERCENT"] = "FIXED"
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    items: list[OrderItemIn] = Field(min_length=1)
    # Customer / delivery details (Telegram bot, QR delivery, ...).
    customer_name: str | None = Field(default=None, max_length=100)
    customer_phone: str | None = Field(default=None, max_length=20)
    delivery_type: Literal["DELIVERY", "PICKUP"] | None = None
    delivery_address: str | None = Field(default=None, max_length=500)
    delivery_lat: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    delivery_lng: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    delivery_note: str | None = Field(default=None, max_length=300)
    payment_method: Literal["CASH", "CARD_TRANSFER", "PAYME"] | None = None

    @model_validator(mode="after")
    def _delivery_needs_an_address(self):
        if self.delivery_type == "DELIVERY" and not (self.delivery_address or "").strip():
            raise ValueError("A delivery order needs a delivery address.")
        if (self.delivery_lat is None) != (self.delivery_lng is None):
            raise ValueError("Latitude and longitude must be given together.")
        return self


class OrderDiscountUpdate(BaseModel):
    discount_type: Literal["FIXED", "PERCENT"] = "FIXED"
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class OrderTableTransfer(BaseModel):
    table_id: uuid.UUID


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
    discount_type: str
    discount: Decimal
    tax: Decimal
    service_charge: Decimal
    total: Decimal
    currency: str
    notes: str | None
    waiter_user_id: uuid.UUID | None
    waiter_name: str | None = None
    created_by_user_id: uuid.UUID | None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    bill_requested_at: datetime | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    delivery_type: str | None = None
    delivery_address: str | None = None
    delivery_lat: Decimal | None = None
    delivery_lng: Decimal | None = None
    delivery_note: str | None = None
    payment_method: str | None = None
    payment_proof_url: str | None = None
    items: list[OrderItemOut] = []
    created_at: datetime


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(DRAFT|OPEN|COMPLETED|CANCELLED|PARTIALLY_PAID|REFUNDED)$")


class KitchenStatusUpdate(BaseModel):
    kitchen_status: str = Field(pattern="^(NEW|PREPARING|READY|SERVED)$")


class WaiterStatsOut(BaseModel):
    waiter_user_id: uuid.UUID
    date_from: datetime
    date_to: datetime
    total_sales: Decimal
    order_count: int
    tables_served: int
    average_check: Decimal
    cancelled_count: int