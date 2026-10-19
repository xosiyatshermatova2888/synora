"""Public (unauthenticated) QR-menu API — the one place in the API that's
deliberately open with no auth dependency on any route. Tenant resolution
happens per-request from the URL (`restaurant_slug`), never from a JWT
claim; see `app/services/public_menu.py` for the fail-closed lookups."""

import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip
from app.database.session import get_db
from app.schemas.orders import OrderCreate
from app.schemas.public import PublicMenuOut, PublicOrderCreate, PublicOrderOut, PublicTableOut
from app.services import customers as customers_service
from app.services import orders as order_service
from app.services import public_menu as public_menu_service
from app.utils.errors import RateLimitedError
from app.utils.rate_limit import public_order_limit_hit, record_public_order_attempt

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/menu/{restaurant_slug}", response_model=PublicMenuOut)
async def public_menu(restaurant_slug: str, db: AsyncSession = Depends(get_db)):
    return await public_menu_service.get_public_menu(db, restaurant_slug)


@router.get("/tables/{restaurant_slug}/{branch_id}", response_model=list[PublicTableOut])
async def public_tables(restaurant_slug: str, branch_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await public_menu_service.get_public_tables(db, restaurant_slug, branch_id)


@router.post("/orders", response_model=PublicOrderOut, status_code=201)
async def create_public_order(
    payload: PublicOrderCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    ip = await get_client_ip(request)
    if public_order_limit_hit(ip):
        raise RateLimitedError(detail="Too many orders from this connection. Please wait a moment.")
    record_public_order_attempt(ip)

    restaurant = await public_menu_service.resolve_restaurant(db, payload.restaurant_slug)
    await public_menu_service.resolve_branch(db, restaurant.id, payload.branch_id)
    await public_menu_service.resolve_table(db, restaurant.id, payload.branch_id, payload.table_id)

    customer = await customers_service.find_or_create(
        db,
        restaurant.id,
        phone=payload.customer_phone,
        full_name=payload.customer_name,
    )

    order = await order_service.create_order(
        db,
        restaurant.id,
        None,
        OrderCreate(
            branch_id=payload.branch_id,
            table_id=payload.table_id,
            source="QR",
            notes=payload.notes,
            items=payload.items,
        ),
        idempotency_key=idempotency_key,
        customer_id=customer.id,
    )
    return PublicOrderOut(order_number=order.order_number, total=order.total, currency=order.currency)
