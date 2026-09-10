import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, uuid_pk


class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)  # ISO 4217
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
# Audit: who created this restaurant. Plain column (no DB FK): it points at
    # users.id which itself references restaurants.id (a circular FK Postgres
    # cannot define in one migration). Referential integrity on this audit
    # field is enforced by the application layer.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    branches = relationship("Branch", back_populates="restaurant", lazy="selectin")
    users = relationship("User", back_populates="restaurant", lazy="selectin")