"""Order Engine API (Phase G).

Create is idempotent via the `Idempotency-Key` header (Section 11). Status and
kitchen-status transitions go through the single state-machine functions in
`app/services/orders.py` (Section 12) — never raw status sets in routes.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant,
    get_current_user,
    get_current_user_restaurant,
    require_permission,
)
from app.database.session import get_db
from app.models.user import User
from app.repositories.orders import OrderRepository
from app.schemas.common import Page, clamp_pagination
from app.schemas.printing import PrintJobOut
from app.schemas.orders import (
    KitchenStatusUpdate,
    OrderCreate,
    OrderDiscountUpdate,
    OrderOut,
    OrderStatusUpdate,
    OrderTableTransfer,
    WaiterStatsOut,
)
from app.schemas.split_bill import SplitPreviewOut, SplitPreviewRequest
from app.services import orders as order_service
from app.services import printing as printing_service
from app.services import split_bill as split_bill_service
from app.utils.errors import ForbiddenError

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


def _stats_window(date_from: datetime | None, date_to: datetime | None) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    resolved_to = date_to or now
    resolved_from = date_from or resolved_to.replace(hour=0, minute=0, second=0, microsecond=0)
    return resolved_from, resolved_to


@router.get("/stats/me", response_model=WaiterStatsOut)
async def my_waiter_stats(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
):
    resolved_from, resolved_to = _stats_window(date_from, date_to)
    return await order_service.waiter_stats(
        db, current_tenant, current_user.id, resolved_from, resolved_to
    )


@router.get("/stats/{waiter_user_id}", response_model=WaiterStatsOut)
async def waiter_stats_for(
    waiter_user_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.read")),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
):
    resolved_from, resolved_to = _stats_window(date_from, date_to)
    return await order_service.waiter_stats(
        db, current_tenant, waiter_user_id, resolved_from, resolved_to
    )


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    return await OrderRepository(db).get_or_404(current_tenant, order_id)


# Moving an order to these states has money consequences, so `orders.update`
# (which waiters and kitchen staff hold) is not enough on its own.
STATUS_PERMISSION = {
    "CANCELLED": "orders.cancel",
    "COMPLETED": "payments.create",
    "PARTIALLY_PAID": "payments.create",
    "REFUNDED": "finance.manage",
}


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    auth: tuple[User, dict] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    needed = STATUS_PERMISSION.get(payload.status)
    if needed and needed not in (auth[1].get("perms") or []):
        raise ForbiddenError(detail=f"Permission '{needed}' required to set status {payload.status}.")
    return await order_service.transition_order(
        db, current_tenant, order_id, payload.status, current_user_id=current_user.id
    )


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


@router.patch("/{order_id}/discount", response_model=OrderOut)
async def update_order_discount(
    order_id: uuid.UUID,
    payload: OrderDiscountUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user_restaurant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.discount")),
):
    return await order_service.apply_discount(
        db, current_tenant, order_id, payload.discount_type, payload.discount, current_user_id=current_user.id
    )


@router.patch("/{order_id}/table", response_model=OrderOut)
async def transfer_order_table(
    order_id: uuid.UUID,
    payload: OrderTableTransfer,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    return await order_service.transfer_table(db, current_tenant, order_id, payload.table_id)


@router.post("/{source_order_id}/merge-into/{target_order_id}", response_model=OrderOut)
async def merge_order_into(
    source_order_id: uuid.UUID,
    target_order_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    return await order_service.merge_orders(
        db, current_tenant, source_order_id, target_order_id
    )


@router.post("/{order_id}/split-preview", response_model=SplitPreviewOut)
async def preview_order_split(
    order_id: uuid.UUID,
    payload: SplitPreviewRequest,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
):
    order = await OrderRepository(db).get_or_404(current_tenant, order_id)
    return split_bill_service.preview_split(order, payload)


@router.post("/{order_id}/request-bill", response_model=OrderOut)
async def request_order_bill(
    order_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    """Waiter -> cashier: bring this table's bill."""
    return await order_service.request_bill(db, current_tenant, order_id)


@router.post("/{order_id}/print", response_model=PrintJobOut)
async def print_order_document(
    order_id: uuid.UUID,
    kind: Literal["PRECHECK", "RECEIPT"] = Query(),
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    """Cashier: print the pre-check ("hisob") or the final receipt on the
    branch's receipt printer. Returns the job so the UI can show a failure."""
    return await printing_service.print_order(db, current_tenant, order_id, kind)


@router.post("/{order_id}/reprint-kitchen", response_model=PrintJobOut)
async def reprint_kitchen_ticket(
    order_id: uuid.UUID,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    return await printing_service.print_order(db, current_tenant, order_id, "KITCHEN_TICKET")
