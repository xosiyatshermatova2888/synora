"""Payments + cash shifts.

Multi-payment per order from day one: `payments` is its own table keyed to
`order_id`, never a single `amount_paid` column on `orders` (Section 14) — split
payments later is a UI concern, not a migration. Money is Numeric(12,2)/Decimal
(Section 12A).

Cash shifts carry a `version` for optimistic locking so concurrent close
requests cannot double-process the closing balance (Section 15).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, uuid_pk

PAYMENT_METHODS = ("CASH", "CARD", "TRANSFER", "QR")

CASH_SHIFT_STATUSES = ("OPEN", "CLOSED")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Tenant scope: NOT NULL + index (Section 5A).
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), default="CASH", nullable=False)
    # Internal record only — real payment gateways are deferred (Section 14).
    status: Mapped[str] = mapped_column(String(20), default="PAID", nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    # Provider reconciliation fields (Phase M): "PAYME" (or "CLICK" later).
    # provider_transaction_id is Payme's transaction id; the unique constraint
    # below is the idempotency key for webhook redelivery.
    provider: Mapped[str | None] = mapped_column(String(20))
    provider_transaction_id: Mapped[str | None] = mapped_column(String(100))
    provider_state: Mapped[str | None] = mapped_column(String(30))
    provider_raw: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_payments_provider_txn",
        ),
    )

    order = relationship("Order", back_populates="payments")


class CashShift(Base, TimestampMixin):
    __tablename__ = "cash_shifts"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cashier_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Money: Numeric(12,2)/Decimal everywhere.
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    expected_closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    actual_closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    # Optimistic locking (Section 15): concurrent close must not double-process.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)