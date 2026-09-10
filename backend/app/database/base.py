import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLAlchemy's portable Uuid: renders as native UUID on PostgreSQL and a
# CHAR(32) hex string on other backends (eg aiosqlite in headless tests),
# converting uuid.UUID <-> stored representation on bind/result.
UUID_COLUMN = Uuid()


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid(),
        primary_key=True,
        default=uuid.uuid4,
    )


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )