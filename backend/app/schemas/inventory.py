import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InventoryTransactionType = Literal["IN", "OUT", "ADJUSTMENT"]


class InventoryItemCreate(BaseModel):
    branch_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    unit: str = Field(min_length=1, max_length=20)
    minimum_quantity: Decimal = Field(default=Decimal("0.000"), ge=0, decimal_places=3)
    cost_per_unit: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    supplier: str | None = None


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    minimum_quantity: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    cost_per_unit: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    supplier: str | None = None
    is_active: bool | None = None


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    unit: str
    quantity: Decimal
    minimum_quantity: Decimal
    cost_per_unit: Decimal
    supplier: str | None
    is_active: bool
    is_low_stock: bool = False


class InventoryTransactionCreate(BaseModel):
    type: InventoryTransactionType
    quantity: Decimal = Field(gt=0, decimal_places=3)
    reason: str | None = None


class InventoryTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    inventory_item_id: uuid.UUID
    type: str
    quantity: Decimal
    reason: str | None
    created_by_user_id: uuid.UUID | None
    created_at: datetime
