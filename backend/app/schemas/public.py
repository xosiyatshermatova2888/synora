"""Public (unauthenticated) QR-menu schemas.

Deliberately leaner than the dashboard's `schemas/menu.py` equivalents —
`cost_price` (internal procurement cost) is never exposed to a customer.
"""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.menu import ModifierGroupOut
from app.schemas.orders import OrderItemIn


class PublicProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    modifier_groups: list[ModifierGroupOut] = []


class PublicCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    image_url: str | None
    products: list[PublicProductOut] = []


class PublicBranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    address: str | None


class PublicMenuOut(BaseModel):
    restaurant_name: str
    currency: str
    branches: list[PublicBranchOut]
    categories: list[PublicCategoryOut]


class PublicTableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    capacity: int


class PublicOrderCreate(BaseModel):
    restaurant_slug: str
    branch_id: uuid.UUID
    table_id: uuid.UUID
    customer_name: str = Field(min_length=1, max_length=150)
    customer_phone: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    items: list[OrderItemIn] = Field(min_length=1)


class PublicOrderOut(BaseModel):
    order_number: int
    total: Decimal
    currency: str
