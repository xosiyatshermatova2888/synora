"""Kitchen module API (Phase K).

Tickets are a view over the central order (Section 34) — advancing a ticket's
status funnels through the single order state machine in `app/services/orders.py`
inside ONE transaction and then emits the kitchen WebSocket event (Section 21:
broadcast only after a successful commit).

Permissions reuse the existing `orders.*` codes — `orders.read` to view the
board, `orders.update` to advance it (the KITCHEN role already has both). Stations
are configuration, created under the same `users.manage` gate as tables.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, require_permission
from app.database.session import get_db
from app.models.kitchen import KitchenStation
from app.repositories.kitchen import KitchenStationRepository, KitchenTicketRepository
from app.schemas.kitchen import (
    KitchenStationCreate,
    KitchenStationOut,
    KitchenTicketOut,
    KitchenTicketStatusUpdate,
)
from app.services import kitchen as kitchen_service

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


@router.get("/tickets", response_model=list[KitchenTicketOut])
async def list_kitchen_tickets(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
    branch_id: uuid.UUID = Query(...),
):
    """Active board tickets for one branch. Cross-tenant branches return [] —
    the tenant clause always applies (Section 5A)."""
    tickets = await KitchenTicketRepository(db).list_active_for_branch(
        current_tenant, branch_id
    )
    return [kitchen_service.serialize(t) for t in tickets]


@router.patch("/tickets/{ticket_id}/status", response_model=KitchenTicketOut)
async def update_ticket_status(
    ticket_id: uuid.UUID,
    payload: KitchenTicketStatusUpdate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.update")),
):
    return await kitchen_service.advance_ticket_status(
        db, current_tenant, ticket_id, payload.status
    )


@router.get("/stations", response_model=list[KitchenStationOut])
async def list_stations(
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("orders.read")),
    branch_id: uuid.UUID | None = Query(default=None),
):
    return await KitchenStationRepository(db).list_for_branch(current_tenant, branch_id)


@router.post("/stations", response_model=KitchenStationOut, status_code=201)
async def create_station(
    payload: KitchenStationCreate,
    current_tenant: uuid.UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("users.manage")),
):
    station = KitchenStation(
        restaurant_id=current_tenant,
        branch_id=payload.branch_id,
        name=payload.name,
    )
    db.add(station)
    await db.flush()
    await db.commit()
    await db.refresh(station)
    return station