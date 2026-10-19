"""Inventory API — stock items + kirim/chiqim/adjustment transactions.

Gated by the `inventory.read`/`inventory.manage` permissions, which existed
as stubs (granted to OWNER/ADMIN/MANAGER) with no feature behind them until
this module.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_current_user_restaurant, require_feature, require_permission
from app.database.session import get_db
from app.utils.tenant_refs import require_branch
from app.models.inventory import InventoryItem
from app.models.user import User
from app.repositories.inventory import InventoryItemRepository, InventoryTransactionRepository
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemUpdate,
    InventoryTransactionCreate,
    InventoryTransactionOut,
)
from app.services import inventory as inventory_service

router = APIRouter(
    prefix="/inventory-items", tags=["inventory"], dependencies=[Depends(require_feature("inventory"))]
)


@router.get("", response_model=list[InventoryItemOut])
async def list_inventory_items(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("inventory.read")),
    branch_id: uuid.UUID | None = Query(default=None),
):
    return await InventoryItemRepository(db).list_for_branch(current_tenant, branch_id)


@router.post("", response_model=InventoryItemOut, status_code=201)
async def create_inventory_item(
    payload: InventoryItemCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("inventory.manage")),
):
    await require_branch(db, current_tenant, payload.branch_id)
    item = InventoryItem(restaurant_id=current_tenant, **payload.model_dump())
    db.add(item)
    await db.flush()
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    item_id: uuid.UUID,
    payload: InventoryItemUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("inventory.manage")),
):
    repo = InventoryItemRepository(db)
    item = await repo.get_or_404(current_tenant, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.flush()
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/{item_id}/transactions", response_model=InventoryItemOut)
async def add_inventory_transaction(
    item_id: uuid.UUID,
    payload: InventoryTransactionCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("inventory.manage")),
):
    return await inventory_service.record_transaction(
        db,
        current_tenant,
        item_id,
        payload.type,
        payload.quantity,
        payload.reason,
        current_user.id,
    )


@router.get("/{item_id}/transactions", response_model=list[InventoryTransactionOut])
async def list_inventory_transactions(
    item_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("inventory.read")),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await InventoryTransactionRepository(db).list_for_item(
        current_tenant, item_id, limit=limit, offset=offset
    )
