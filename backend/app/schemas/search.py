import uuid
from decimal import Decimal

from pydantic import BaseModel


class SearchOrderHit(BaseModel):
    id: uuid.UUID
    order_number: int
    status: str
    total: Decimal


class SearchProductHit(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal


class SearchCustomerHit(BaseModel):
    id: uuid.UUID
    full_name: str | None
    phone: str | None


class SearchStaffHit(BaseModel):
    id: uuid.UUID
    full_name: str
    username: str


class SearchTableHit(BaseModel):
    id: uuid.UUID
    name: str
    zone: str | None


class SearchResultsOut(BaseModel):
    orders: list[SearchOrderHit]
    products: list[SearchProductHit]
    customers: list[SearchCustomerHit]
    staff: list[SearchStaffHit]
    tables: list[SearchTableHit]
