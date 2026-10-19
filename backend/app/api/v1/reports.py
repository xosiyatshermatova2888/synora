"""Reports/Analytics API — real SQL aggregation, gated by the existing
(previously unused) `analytics.read` permission."""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_feature, require_permission
from app.database.session import get_db
from app.schemas.reports import (
    ExpenseReportRow,
    PaymentReportRow,
    ProductReportRow,
    ProfitReportOut,
    SalesSeriesOut,
    WaiterReportRow,
)
from app.services import reports as reports_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _default_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    resolved_to = date_to or date.today()
    resolved_from = date_from or (resolved_to - timedelta(days=6))
    return resolved_from, resolved_to


@router.get("/sales", response_model=SalesSeriesOut)
async def get_sales_series(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("analytics.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    group_by: str = Query(default="day", pattern="^(day|week|month)$"),
):
    resolved_from, resolved_to = _default_range(date_from, date_to)
    points = await reports_service.sales_series(
        db, current_tenant, branch_id, resolved_from, resolved_to, group_by
    )
    return {"group_by": group_by, "points": points}


@router.get("/products", response_model=list[ProductReportRow])
async def get_product_report(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("analytics.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    resolved_from, resolved_to = _default_range(date_from, date_to)
    return await reports_service.product_report(db, current_tenant, branch_id, resolved_from, resolved_to)


@router.get("/waiters", dependencies=[Depends(require_feature("advanced_reports"))], response_model=list[WaiterReportRow])
async def get_waiter_report(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("analytics.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    resolved_from, resolved_to = _default_range(date_from, date_to)
    return await reports_service.waiter_report(db, current_tenant, branch_id, resolved_from, resolved_to)


@router.get("/payments", response_model=list[PaymentReportRow])
async def get_payment_report(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("analytics.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    resolved_from, resolved_to = _default_range(date_from, date_to)
    return await reports_service.payment_report(db, current_tenant, branch_id, resolved_from, resolved_to)


@router.get("/expenses", dependencies=[Depends(require_feature("advanced_reports"))], response_model=list[ExpenseReportRow])
async def get_expense_report(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("analytics.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    resolved_from, resolved_to = _default_range(date_from, date_to)
    return await reports_service.expense_report(db, current_tenant, branch_id, resolved_from, resolved_to)


@router.get("/profit", dependencies=[Depends(require_feature("advanced_reports"))], response_model=ProfitReportOut)
async def get_profit_report(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("analytics.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    resolved_from, resolved_to = _default_range(date_from, date_to)
    return await reports_service.profit_report(db, current_tenant, branch_id, resolved_from, resolved_to)
