"""Menu API (Phase E). Category/Product/ModifierGroup/Modifier CRUD.

Permissions map to the seeded codes (Section 7A): read for menu.read,
create for menu.create, update for menu.update, delete (soft) for menu.delete.
Every route is tenant-scoped via `get_current_tenant` (Section 5A).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user_restaurant, require_permission
from app.database.session import get_db
from app.models.menu import Category, Modifier, ModifierGroup, Product
from app.models.user import User
from app.repositories.menu import (
    CategoryRepository,
    ModifierGroupRepository,
    ProductRepository,
)
from app.schemas.menu import (
    CategoryCreate,
    CategoryOut,
    CategoryTreeOut,
    CategoryUpdate,
    ModifierCreate,
    ModifierGroupCreate,
    ModifierGroupOut,
    ModifierGroupUpdate,
    ModifierOut,
    ModifierUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from app.schemas.common import Page, PaginationParams, clamp_pagination
from app.services import menu as menu_service
from app.utils.errors import NotFoundError

router = APIRouter(prefix="/menu", tags=["menu"])


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.read")),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    limit, offset = clamp_pagination(limit, offset)
    return await CategoryRepository(db).list_active(current_tenant, limit=limit, offset=offset)


@router.get("/categories/tree", response_model=Page[CategoryTreeOut])
async def category_tree(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.read")),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Categories with nested products — the frontend menu browser shape."""
    limit, offset = clamp_pagination(limit, offset)
    repo = CategoryRepository(db)
    categories = await repo.list_active(current_tenant, limit=limit, offset=offset)
    total = await repo.count(current_tenant)
    return Page(items=categories, total=total, limit=limit, offset=offset)


@router.post("/categories", response_model=CategoryOut, status_code=201)
async def create_category(
    payload: CategoryCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.create")),
):
    category = await menu_service.create_category(db, current_tenant, payload)
    await db.commit()
    await db.refresh(category)
    return category


@router.get("/categories/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.read")),
):
    return await CategoryRepository(db).get_or_404(current_tenant, category_id)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.update")),
):
    category = await menu_service.update_category(db, current_tenant, category_id, payload)
    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.delete")),
):
    await menu_service.delete_category(db, current_tenant, category_id)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@router.get("/products", response_model=Page[ProductOut])
async def list_products(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.read")),
    category_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    limit, offset = clamp_pagination(limit, offset)
    repo = ProductRepository(db)
    stmt = select(Product).where(
        Product.restaurant_id == current_tenant, Product.deleted_at.is_(None)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    items = list((await db.scalars(stmt.order_by(Product.name).limit(limit).offset(offset))).all())
    total_stmt = select(func.count()).select_from(Product).where(
        Product.restaurant_id == current_tenant, Product.deleted_at.is_(None)
    )
    if category_id is not None:
        total_stmt = total_stmt.where(Product.category_id == category_id)
    total = await db.scalar(total_stmt) or 0
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.create")),
):
    product = await menu_service.create_product(db, current_tenant, payload)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.read")),
):
    return await ProductRepository(db).get_or_404(current_tenant, product_id)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.update")),
):
    price_changed = "price" in payload.model_fields_set
    product = await menu_service.update_product(db, current_tenant, product_id, payload)
    await db.commit()
    await db.refresh(product)

    if price_changed:
        from app.services import audit as audit_service

        await audit_service.log_action(
            db, current_tenant, current_user.id, "product.price_update", "product", product.id,
            f"Changed {product.name}'s price to {product.price}",
        )

    return product


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.delete")),
):
    await menu_service.delete_product(db, current_tenant, product_id)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Modifier groups + modifiers
# ---------------------------------------------------------------------------
@router.get("/modifier-groups", response_model=list[ModifierGroupOut])
async def list_modifier_groups(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.read")),
):
    return await ModifierGroupRepository(db).list_active(current_tenant)


@router.post("/modifier-groups", response_model=ModifierGroupOut, status_code=201)
async def create_modifier_group(
    payload: ModifierGroupCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.create")),
):
    group = await menu_service.create_modifier_group(db, current_tenant, payload)
    await db.commit()
    await db.refresh(group)
    return group


@router.patch("/modifier-groups/{group_id}", response_model=ModifierGroupOut)
async def update_modifier_group(
    group_id: uuid.UUID,
    payload: ModifierGroupUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.update")),
):
    group = await menu_service.update_modifier_group(db, current_tenant, group_id, payload)
    await db.commit()
    await db.refresh(group)
    return group


@router.post("/modifier-groups/{group_id}/modifiers", response_model=ModifierOut, status_code=201)
async def add_modifier(
    group_id: uuid.UUID,
    payload: ModifierCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.create")),
):
    modifier = await menu_service.add_modifier(db, current_tenant, group_id, payload)
    await db.commit()
    await db.refresh(modifier)
    return modifier


@router.patch("/modifiers/{modifier_id}", response_model=ModifierOut)
async def update_modifier(
    modifier_id: uuid.UUID,
    payload: ModifierUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("menu.update")),
):
    modifier = await menu_service.update_modifier(db, current_tenant, modifier_id, payload)
    await db.commit()
    await db.refresh(modifier)
    return modifier