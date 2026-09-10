"""Menu domain: Category, Product, ModifierGroup, Modifier.

Money fields (`price`, `cost_price`) are `Numeric(12,2)` / Python `Decimal` —
never float (master spec Section 9/12A). Category/Product carry an `image_url`
(Future module: uploads, Section 30). Category/product deletion is a SOFT delete
(`deleted_at`) so historical orders referencing them stay intact (Section 20).

Branch-specific pricing is a future extension point (`branch_price_overrides`,
Section 9) — NOT built now.
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
    Table,
    Text,
    Column,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, uuid_pk

product_modifier_groups = Table(
    "product_modifier_groups",
    Base.metadata,
    Column(
        "product_id",
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "modifier_group_id",
        ForeignKey("modifier_groups.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Tenant scope: NOT NULL + index (Section 5A).
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    products = relationship(
        "Product",
        back_populates="category",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Money: Numeric(12,2) / Decimal, never float (Section 9).
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category = relationship("Category", back_populates="products")
    modifier_groups = relationship(
        "ModifierGroup", secondary="product_modifier_groups", lazy="selectin"
    )


class ModifierGroup(Base, TimestampMixin):
    __tablename__ = "modifier_groups"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # selection policy (Section 9): required/optional, min/max.
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_selections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_selections: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    modifiers = relationship(
        "Modifier",
        back_populates="group",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Modifier.sort_order",
    )


class Modifier(Base, TimestampMixin):
    __tablename__ = "modifiers"

    id: Mapped[uuid.UUID] = uuid_pk()
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modifier_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modifier_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group = relationship("ModifierGroup", back_populates="modifiers")