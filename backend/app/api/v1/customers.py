"""Customer/CRM API — read-only from the dashboard's point of view; rows are
created by the unauthenticated order channels (`app/services/customers.py::
find_or_create`, called from `api/v1/public.py`), not from here."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_feature, require_permission
from app.database.session import get_db
from app.schemas.customers import CustomerDetailOut, CustomerOut
from app.services import customers as customers_service

router = APIRouter(
    prefix="/customers", tags=["customers"], dependencies=[Depends(require_feature("crm"))]
)


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.read")),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await customers_service.list_customers(
        db, current_tenant, search=search, limit=limit, offset=offset
    )


@router.get("/{customer_id}", response_model=CustomerDetailOut)
async def get_customer(
    customer_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.read")),
):
    return await customers_service.get_customer_detail(db, current_tenant, customer_id)
