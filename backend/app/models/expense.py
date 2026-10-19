"""Expense domain: a flat expense ledger for the owner's cost side.

Categories match the spec's own expense-report breakdown (rent/salary/
product/utilities/other). `expense_date` is separate from the row's
`created_at` — an expense is often logged after the fact (e.g. entering last
month's rent invoice today), so the report date range must filter on
`expense_date`, not creation time.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk

EXPENSE_CATEGORIES = ("RENT", "SALARY", "PRODUCT", "UTILITIES", "OTHER")


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
