"""Table domain.

Optimistic locking (Section 10): a `version` integer, incremented on every
update. Two waiters double-booking the same table under concurrency is
impossible — the second writer's stale `version` fails the WHERE clause and the
transaction rolls back / raises ConflictError.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, uuid_pk


class Table(Base, TimestampMixin):
    __tablename__ = "tables"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Tenant scope: NOT NULL + index (Section 5A).
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # "Table 1", "A4"
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    # AVAILABLE | OCCUPIED | RESERVED | DISABLED (Section 10).
    status: Mapped[str] = mapped_column(String(20), default="AVAILABLE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Optimistic locking (Section 10): incremented on every update.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)