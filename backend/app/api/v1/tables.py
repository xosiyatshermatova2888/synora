"""Table API (Phase F). Status transitions are optimistic-lock-safe (Section 10):
the client sends the `version` it read; a concurrent writer fails with 409."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_permission
from app.database.session import get_db
from app.models.table import Table
from app.repositories.tables import TableRepository
from app.schemas.tables import TableCreate, TableOut, TableUpdate

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("", response_model=list[TableOut])
async def list_tables(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
):
    repo = TableRepository(db)
    if branch_id is not None:
        tables = await repo.list_for_branch(current_tenant, branch_id)
    else:
        tables = list(
            (await db.scalars(
                select(Table).where(
                    Table.restaurant_id == current_tenant, Table.is_active.is_(True)
                ).order_by(Table.name)
            )).all()
        )
    if status is not None:
        tables = [t for t in tables if t.status == status]
    return tables


@router.post("", response_model=TableOut, status_code=201)
async def create_table(
    payload: TableCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    table = Table(
        restaurant_id=current_tenant,
        branch_id=payload.branch_id,
        name=payload.name,
        zone=payload.zone,
        capacity=payload.capacity,
    )
    db.add(table)
    await db.flush()
    await db.commit()
    await db.refresh(table)
    return table


@router.get("/{table_id}", response_model=TableOut)
async def get_table(
    table_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    return await TableRepository(db).get_or_404(current_tenant, table_id)


@router.patch("/{table_id}", response_model=TableOut)
async def update_table(
    table_id: uuid.UUID,
    payload: TableUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    repo = TableRepository(db)
    table = await repo.get_or_404(current_tenant, table_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(table, field, value)
    table.version += 1
    await db.flush()
    await db.commit()
    await db.refresh(table)
    return table