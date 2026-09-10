"""Menu repositories. Every method requires restaurant_id (Section 5A)."""

import uuid

from sqlalchemy import or_, select

from app.models.menu import Category, Modifier, ModifierGroup, Product
from app.repositories.base import TenantScopedRepository
from app.utils.errors import NotFoundError


class CategoryRepository(TenantScopedRepository[Category]):
    model = Category

    async def list_active(self, restaurant_id: uuid.UUID, *, limit: int = 20, offset: int = 0) -> list[Category]:
        stmt = (
            select(self.model)
            .where(self.model.restaurant_id == restaurant_id, self.model.deleted_at.is_(None))
            .order_by(self.model.sort_order, self.model.name)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.scalars(stmt)).all())

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> Category:
        category = await self.get(restaurant_id, id)
        if category is None or category.deleted_at is not None:
            raise NotFoundError(detail="Category not found in this restaurant.")
        return category

    async def soft_delete(self, restaurant_id: uuid.UUID, category: Category) -> None:
        from datetime import datetime, timezone

        if category.restaurant_id != restaurant_id:
            raise NotFoundError(detail="Category not found in this restaurant.")
        category.deleted_at = datetime.now(timezone.utc)
        category.is_active = False
        await self.session.flush()


class ProductRepository(TenantScopedRepository[Product]):
    model = Product

    async def list_active(self, restaurant_id: uuid.UUID, *, limit: int = 20, offset: int = 0) -> list[Product]:
        stmt = (
            select(self.model)
            .where(self.model.restaurant_id == restaurant_id, self.model.deleted_at.is_(None))
            .order_by(self.model.name)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.scalars(stmt)).all())

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> Product:
        product = await self.get(restaurant_id, id)
        if product is None or product.deleted_at is not None:
            raise NotFoundError(detail="Product not found in this restaurant.")
        return product

    async def soft_delete(self, restaurant_id: uuid.UUID, product: Product) -> None:
        from datetime import datetime, timezone

        if product.restaurant_id != restaurant_id:
            raise NotFoundError(detail="Product not found in this restaurant.")
        product.deleted_at = datetime.now(timezone.utc)
        product.is_active = False
        await self.session.flush()

    async def list_by_ids(self, restaurant_id: uuid.UUID, ids: list[uuid.UUID]) -> list[Product]:
        stmt = select(self.model).where(
            self.model.restaurant_id == restaurant_id,
            self.model.id.in_(ids),
            self.model.deleted_at.is_(None),
        )
        return list((await self.session.scalars(stmt)).all())


class ModifierGroupRepository(TenantScopedRepository[ModifierGroup]):
    model = ModifierGroup

    async def list_active(self, restaurant_id: uuid.UUID, *, limit: int = 50, offset: int = 0) -> list[ModifierGroup]:
        stmt = (
            select(self.model)
            .where(self.model.restaurant_id == restaurant_id, self.model.is_active.is_(True))
            .order_by(self.model.name)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.scalars(stmt)).all())

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> ModifierGroup:
        group = await self.get(restaurant_id, id)
        if group is None or not group.is_active:
            raise NotFoundError(detail="Modifier group not found in this restaurant.")
        return group


class ModifierRepository(TenantScopedRepository[Modifier]):
    model = Modifier

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> Modifier:
        modifier = await self.get(restaurant_id, id)
        if modifier is None or not modifier.is_active:
            raise NotFoundError(detail="Modifier not found in this restaurant.")
        return modifier

    async def list_by_ids(self, restaurant_id: uuid.UUID, ids: list[uuid.UUID]) -> list[Modifier]:
        stmt = select(self.model).where(
            self.model.restaurant_id == restaurant_id,
            self.model.id.in_(ids),
            self.model.is_active.is_(True),
        )
        return list((await self.session.scalars(stmt)).all())