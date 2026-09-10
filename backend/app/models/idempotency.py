"""Order-creation idempotency (Section 11).

A client-generated idempotency key (e.g. a UUID header) is stored with the
created order id. A repeated key within the retention window returns the ORIGINAL
order instead of creating a new one — a flaky waiter-app network retry cannot
create two identical orders. Expired rows are pruned opportunistically.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk


class IdempotencyKey(Base, TimestampMixin):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Client-generated key (unique per restaurant within its window).
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )