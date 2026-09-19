"""Order Engine API (Phase G).

Create is idempotent via the `Idempotency-Key` header (Section 11). Status and
kitchen-status transitions go through the single state-machine functions in
`app/services/orders.py` (Section 12) — never raw status sets in routes.
"""

import uuid

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant,
    get_current_user_restaurant,
    require_permission,
)
from app.database.session import get_db
from app.models.user import User
from app.repositories.orders import OrderRepository
from app.schemas.common import Page, clamp_pagination
from app.schemas.orders import (
    KitchenStatusUpdate,
    OrderCreate,
    OrderOut,
    OrderStatusUpdate,
)
from app.services import orders as order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreate,
    response_idem_header: str | None = Header(default=None, alias="Idempotency-Key"),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.create")),
):
    order = await order_service.create_order(
        db,
        current_tenant,
        current_user.id,
        payload,
        idempotency_key=response_idem_header,
    )
    return order


@router.get("", response_model=Page[OrderOut])
async def list_orders(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
    branch_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    waiter_user_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    limit, offset = clamp_pagination(limit, offset)
    repo = OrderRepository(db)
    items = await repo.list(
        current_tenant,
        branch_id=branch_id,
        status=status,
        waiter_user_id=waiter_user_id,
        limit=limit,
        offset=offset,
    )
    total = await repo.count(
        current_tenant, branch_id=branch_id, status=status, waiter_user_id=waiter_user_id
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/active", response_model=list[OrderOut])
async def active_orders(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
    branch_id: uuid.UUID | None = Query(default=None),
):
    """DRAFT + OPEN + PARTIALLY_PAID orders — the live floor for POS/waiter."""
    repo = OrderRepository(db)
    recent = await repo.list(current_tenant, branch_id=branch_id, limit=200, offset=0)
    return [o for o in recent if o.status in ("DRAFT", "OPEN", "PARTIALLY_PAID")]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    return await OrderRepository(db).get_or_404(current_tenant, order_id)


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    return await order_service.transition_order(db, current_tenant, order_id, payload.status)


@router.patch("/{order_id}/kitchen-status", response_model=OrderOut)
async def update_kitchen_status(
    order_id: uuid.UUID,
    payload: KitchenStatusUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    return await order_service.update_kitchen_status(
        db, current_tenant, order_id, payload.kitchen_status
    )