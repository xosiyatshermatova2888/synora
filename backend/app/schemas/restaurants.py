"""Restaurant + branch schemas (Phase D)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class RestaurantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    status: str | None = Field(default=None, pattern="^(ACTIVE|SUSPENDED|CLOSED)$")
    payment_card_number: str | None = Field(default=None, max_length=32)
    payment_card_holder: str | None = Field(default=None, max_length=100)


class RestaurantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    phone: str | None
    email: str | None
    address: str | None
    timezone: str
    currency: str
    status: str
    is_active: bool
    # Never the raw token/secret — just enough for the Settings page to show
    # connection status and the customer-facing t.me/<username> link.
    telegram_bot_username: str | None = None
    telegram_connected: bool = False
    payment_card_number: str | None = None
    payment_card_holder: str | None = None


class TelegramConnectRequest(BaseModel):
    bot_token: str = Field(min_length=10, max_length=200)


class TelegramStatusOut(BaseModel):
    telegram_connected: bool
    telegram_bot_username: str | None


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str | None = None
    phone: str | None = None
    timezone: str | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = None
    phone: str | None = None
    timezone: str | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    is_active: bool | None = None


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    address: str | None
    phone: str | None
    timezone: str | None
    currency: str | None
    is_active: bool