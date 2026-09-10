"""Menu schemas. Money is Decimal (Numeric(12,2)) — never float (Section 12A)."""

import uuid
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ModifierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    price: Decimal
    sort_order: int
    is_active: bool


class ModifierGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    is_required: bool
    min_selections: int
    max_selections: int
    is_active: bool
    modifiers: list[ModifierOut]


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    description: str | None
    price: Decimal
    cost_price: Decimal
    image_url: str | None
    is_available: bool
    is_active: bool
    modifier_groups: list[ModifierGroupOut] = []


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    description: str | None
    image_url: str | None
    sort_order: int
    is_active: bool
    products: list[ProductOut] = []


class CategoryTreeOut(CategoryOut):
    """Category with nested products for the frontend menu browser."""


class ProductBase(BaseModel):
    category_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    price: Decimal = Field(ge=0, decimal_places=2)
    cost_price: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=500)
    is_available: bool = True
    modifier_group_ids: list[uuid.UUID] = []


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=500)
    is_available: bool | None = None
    is_active: bool | None = None
    modifier_group_ids: list[uuid.UUID] | None = None


class ModifierGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    is_required: bool = False
    min_selections: int = Field(default=0, ge=0)
    max_selections: int = Field(default=1, ge=1)


class ModifierGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_required: bool | None = None
    min_selections: int | None = Field(default=None, ge=0)
    max_selections: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class ModifierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    price: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)
    sort_order: int = Field(default=0, ge=0)


class ModifierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None