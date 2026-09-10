"""Menu CRUD domain logic. Repositories enforce tenant scoping (Section 5A);
services enforce business rules (soft-delete, modifier selection policy)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import Category, Modifier, ModifierGroup, Product
from app.repositories.menu import (
    CategoryRepository,
    ModifierGroupRepository,
    ModifierRepository,
    ProductRepository,
)
from app.schemas.menu import (
    CategoryCreate,
    CategoryUpdate,
    ModifierCreate,
    ModifierGroupCreate,
    ModifierGroupUpdate,
    ModifierUpdate,
    ProductCreate,
    ProductUpdate,
)
from app.utils.errors import NotFoundError, BusinessRuleError


async def create_category(session: AsyncSession, restaurant_id: uuid.UUID, payload: CategoryCreate) -> Category:
    repo = CategoryRepository(session)
    category = Category(restaurant_id=restaurant_id, **payload.model_dump())
    return await repo.add(category)


async def update_category(
    session: AsyncSession, restaurant_id: uuid.UUID, category_id: uuid.UUID, payload: CategoryUpdate
) -> Category:
    repo = CategoryRepository(session)
    category = await repo.get_or_404(restaurant_id, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    return await repo.save(category)


async def delete_category(session: AsyncSession, restaurant_id: uuid.UUID, category_id: uuid.UUID) -> None:
    repo = CategoryRepository(session)
    category = await repo.get_or_404(restaurant_id, category_id)
    await repo.soft_delete(restaurant_id, category)


async def create_product(
    session: AsyncSession, restaurant_id: uuid.UUID, payload: ProductCreate
) -> Product:
    repo = ProductRepository(session)
    group_repo = ModifierGroupRepository(session)
    data = payload.model_dump(exclude={"modifier_group_ids"})
    product = Product(restaurant_id=restaurant_id, **data)
    product = await repo.add(product)
    if payload.modifier_group_ids:
        groups = await _load_groups(session, restaurant_id, payload.modifier_group_ids)
        product.modifier_groups = groups
    await session.flush()
    return await repo.get_or_404(restaurant_id, product.id)


async def update_product(
    session: AsyncSession, restaurant_id: uuid.UUID, product_id: uuid.UUID, payload: ProductUpdate
) -> Product:
    repo = ProductRepository(session)
    product = await repo.get_or_404(restaurant_id, product_id)
    data = payload.model_dump(exclude_unset=True, exclude={"modifier_group_ids"})
    for field, value in data.items():
        setattr(product, field, value)
    if payload.model_fields_set and "modifier_group_ids" in payload.model_fields_set:
        product.modifier_groups = await _load_groups(
            session, restaurant_id, payload.modifier_group_ids or []
        )
    return await repo.save(product)


async def delete_product(session: AsyncSession, restaurant_id: uuid.UUID, product_id: uuid.UUID) -> None:
    repo = ProductRepository(session)
    product = await repo.get_or_404(restaurant_id, product_id)
    await repo.soft_delete(restaurant_id, product)


async def create_modifier_group(
    session: AsyncSession, restaurant_id: uuid.UUID, payload: ModifierGroupCreate
) -> ModifierGroup:
    if payload.max_selections < payload.min_selections:
        raise BusinessRuleError(detail="max_selections must be >= min_selections.")
    repo = ModifierGroupRepository(session)
    group = ModifierGroup(restaurant_id=restaurant_id, **payload.model_dump())
    return await repo.add(group)


async def update_modifier_group(
    session: AsyncSession, restaurant_id: uuid.UUID, group_id: uuid.UUID, payload: ModifierGroupUpdate
) -> ModifierGroup:
    repo = ModifierGroupRepository(session)
    group = await repo.get_or_404(restaurant_id, group_id)
    data = payload.model_dump(exclude_unset=True)
    nmin = data.get("min_selections", group.min_selections)
    nmax = data.get("max_selections", group.max_selections)
    if nmax < nmin:
        raise BusinessRuleError(detail="max_selections must be >= min_selections.")
    for field, value in data.items():
        setattr(group, field, value)
    return await repo.save(group)


async def add_modifier(
    session: AsyncSession, restaurant_id: uuid.UUID, group_id: uuid.UUID, payload: ModifierCreate
) -> Modifier:
    group_repo = ModifierGroupRepository(session)
    await group_repo.get_or_404(restaurant_id, group_id)
    modifier = Modifier(restaurant_id=restaurant_id, modifier_group_id=group_id, **payload.model_dump())
    repo = ModifierRepository(session)
    return await repo.add(modifier)


async def update_modifier(
    session: AsyncSession, restaurant_id: uuid.UUID, modifier_id: uuid.UUID, payload: ModifierUpdate
) -> Modifier:
    repo = ModifierRepository(session)
    modifier = await repo.get_or_404(restaurant_id, modifier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(modifier, field, value)
    return await repo.save(modifier)


async def delete_modifier(session: AsyncSession, restaurant_id: uuid.UUID, modifier_id: uuid.UUID) -> None:
    repo = ModifierRepository(session)
    modifier = await repo.get_or_404(restaurant_id, modifier_id)
    modifier.is_active = False
    await repo.save(modifier)


async def _load_groups(
    session: AsyncSession, restaurant_id: uuid.UUID, group_ids: list[uuid.UUID]
) -> list[ModifierGroup]:
    if not group_ids:
        return []
    groups = list(
        (await session.scalars(
            select(ModifierGroup).where(
                ModifierGroup.restaurant_id == restaurant_id,
                ModifierGroup.id.in_(group_ids),
                ModifierGroup.is_active.is_(True),
            )
        )).all()
    )
    if len(groups) != len(set(group_ids)):
        raise NotFoundError(detail="One or more modifier groups not found in this restaurant.")
    return groups