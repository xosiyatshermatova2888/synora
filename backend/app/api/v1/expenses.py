"""Expense CRUD API — gated by the existing `finance.read`/`finance.manage`
permissions, the same convention as Payments (no new permission codes)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user_restaurant, require_permission
from app.database.session import get_db
from app.utils.tenant_refs import require_branch
from app.models.expense import Expense
from app.models.user import User
from app.repositories.expenses import ExpenseRepository
from app.schemas.expenses import ExpenseCreate, ExpenseOut, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    category: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await ExpenseRepository(db).list_filtered(
        current_tenant,
        branch_id=branch_id,
        category=category,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    payload: ExpenseCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.manage")),
):
    await require_branch(db, current_tenant, payload.branch_id)
    expense = Expense(
        restaurant_id=current_tenant,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(expense)
    await db.flush()
    await db.commit()
    await db.refresh(expense)
    return expense


@router.patch("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.manage")),
):
    repo = ExpenseRepository(db)
    expense = await repo.get_or_404(current_tenant, expense_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    await db.flush()
    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("finance.manage")),
):
    repo = ExpenseRepository(db)
    expense = await repo.get_or_404(current_tenant, expense_id)
    await repo.delete(current_tenant, expense)
    await db.commit()
