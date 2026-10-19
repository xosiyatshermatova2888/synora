import uuid
from datetime import date

from sqlalchemy import select

from app.models.expense import Expense
from app.repositories.base import TenantScopedRepository


class ExpenseRepository(TenantScopedRepository[Expense]):
    model = Expense

    async def list_filtered(
        self,
        restaurant_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Expense]:
        stmt = select(Expense).where(Expense.restaurant_id == restaurant_id)
        if branch_id is not None:
            stmt = stmt.where(Expense.branch_id == branch_id)
        if category is not None:
            stmt = stmt.where(Expense.category == category)
        if date_from is not None:
            stmt = stmt.where(Expense.expense_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Expense.expense_date <= date_to)
        stmt = stmt.order_by(Expense.expense_date.desc()).limit(limit).offset(offset)
        return list((await self.session.scalars(stmt)).all())
