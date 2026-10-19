import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class SalesPoint(BaseModel):
    bucket: date
    revenue: Decimal
    order_count: int


class SalesSeriesOut(BaseModel):
    group_by: Literal["day", "week", "month"]
    points: list[SalesPoint]


class ProductReportRow(BaseModel):
    product_name: str
    quantity: int
    revenue: Decimal


class WaiterReportRow(BaseModel):
    waiter_user_id: uuid.UUID
    waiter_name: str
    total_sales: Decimal
    order_count: int
    average_check: Decimal


class PaymentReportRow(BaseModel):
    method: str
    amount: Decimal
    count: int


class ExpenseReportRow(BaseModel):
    category: str
    amount: Decimal


class ProfitReportOut(BaseModel):
    revenue: Decimal
    expenses: Decimal
    profit: Decimal
