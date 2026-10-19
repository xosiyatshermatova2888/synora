"""Customer domain: a lightweight CRM record captured from unauthenticated
order channels (QR menu, Telegram bot).

No denormalized `total_orders`/`total_spent`/`last_visit` columns — those are
computed on read (same SQL-aggregation pattern as `app/services/reports.py`)
against `Order.customer_id`, so there's nothing to keep in sync. This *is*
the loyalty-ready architecture: a future `LoyaltyAccount` table would key off
`Customer.id`; nothing speculative is added here.
"""

import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    # Telegram's own numeric chat id — the natural dedup key for bot customers.
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
