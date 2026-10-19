"""A restaurant's request to start/extend a paid plan, paid by card transfer and
approved by the SYNORA platform owner.

The model is provider-agnostic on purpose (`status`, `receipt_url`, reviewer):
an automated gateway (Payme/Click) can later create APPROVED rows the same way.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, uuid_pk

PAYMENT_STATUSES = ("PENDING", "APPROVED", "REJECTED")
BILLING_CYCLES = ("MONTHLY", "ANNUAL")


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="PENDING", nullable=False, index=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(Text)  # rejection reason
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
