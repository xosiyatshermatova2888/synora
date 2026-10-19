import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExpenseCategory = Literal["RENT", "SALARY", "PRODUCT", "UTILITIES", "OTHER"]


class ExpenseCreate(BaseModel):
    branch_id: uuid.UUID
    category: ExpenseCategory
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str | None = None
    expense_date: date


class ExpenseUpdate(BaseModel):
    category: ExpenseCategory | None = None
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    description: str | None = None
    expense_date: date | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    branch_id: uuid.UUID
    category: str
    amount: Decimal
    description: str | None
    expense_date: date
    created_by_user_id: uuid.UUID | None
    created_at: datetime
