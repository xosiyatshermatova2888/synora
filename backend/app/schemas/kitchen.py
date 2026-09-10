"""Kitchen schemas (Phase K).

Tickets are rendered enrichments of the central order (Section 34): the board
needs `order_number`, a table name and the item snapshots (Section 13) without
round-tripping to the orders API. No money/price is recomputed here — items are
exactly the order's snapshot values.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

KITCHEN_TICKET_STATUS_PATTERN = "^(NEW|PREPARING|READY|SERVED)$"


class KitchenStationCreate(BaseModel):
    branch_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)


class KitchenStationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    restaurant_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime


class KitchenTicketStatusUpdate(BaseModel):
    status: str = Field(pattern=KITCHEN_TICKET_STATUS_PATTERN)


class KitchenTicketItemModifierOut(BaseModel):
    modifier_name_snapshot: str
    quantity: int


class KitchenTicketItemOut(BaseModel):
    product_name_snapshot: str
    quantity: int
    notes: str | None
    modifiers: list[KitchenTicketItemModifierOut] = []


class KitchenTicketOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    branch_id: uuid.UUID
    order_id: uuid.UUID
    order_number: int
    table_name: str | None
    station_id: uuid.UUID | None
    status: str
    notes: str | None
    source: str
    items: list[KitchenTicketItemOut] = []
    created_at: datetime
    updated_at: datetime