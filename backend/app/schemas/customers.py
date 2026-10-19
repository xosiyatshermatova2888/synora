import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str | None
    phone: str | None
    telegram_user_id: int | None
    created_at: datetime


class CustomerOrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_number: int
    total: Decimal
    status: str
    created_at: datetime


class CustomerDetailOut(BaseModel):
    customer: CustomerOut
    total_orders: int
    total_spent: Decimal
    last_visit: datetime | None
    favorite_products: list[str]
    recent_orders: list[CustomerOrderSummary]
