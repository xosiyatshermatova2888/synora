"""Split-bill preview schemas — stateless calculation, no DB writes.

A split is just "how to divide order.total before paying it"; settlement still
goes through the existing multi-payment `POST /payments` endpoint, once per
resulting share (see `app/services/payments.py::add_payment`).
"""

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class SplitItemGroup(BaseModel):
    label: str
    order_item_ids: list[uuid.UUID] = Field(min_length=1)


class SplitPreviewRequest(BaseModel):
    mode: Literal["person", "item", "amount"]
    # mode="person"
    parts: int | None = Field(default=None, ge=2, le=50)
    # mode="item"
    item_groups: list[SplitItemGroup] | None = None
    # mode="amount"
    amounts: list[Decimal] | None = None


class SplitShare(BaseModel):
    label: str
    amount: Decimal


class SplitPreviewOut(BaseModel):
    mode: str
    order_total: Decimal
    shares: list[SplitShare]
