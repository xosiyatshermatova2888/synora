import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, uuid_pk

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Tenant scope: NOT NULL + index (Section 5A). A user belongs to exactly one
    # restaurant in this phase; multi-restaurant ownership is a future concern.
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Audit: who created this user (Section 6.3).
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    restaurant = relationship("Restaurant", back_populates="users")
    roles = relationship("Role", secondary=user_roles, lazy="selectin")


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = uuid_pk()
    # NULL restaurant_id  => global system template (OWNER, ADMIN, ...).
    # Non-NULL            => restaurant-custom role (extension point, no UI yet).
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions = relationship("Permission", secondary="role_permissions", lazy="selectin")


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255))