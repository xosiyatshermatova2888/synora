"""Kitchen repositories (tenant-scoped, Phase K).

Listing queries join back to `orders` (via the `order` relationship) so a ticket
stays a VIEW over the single central Order Engine (Section 34) — no kitchen
table ever duplicates order/line-item data.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.kitchen import (
    KITCHEN_TICKET_ACTIVE,
    KitchenStation,
    KitchenTicket,
)
from app.repositories.base import TenantScopedRepository
from app.utils.errors import NotFoundError


class KitchenTicketRepository(TenantScopedRepository[KitchenTicket]):
    model = KitchenTicket

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> KitchenTicket:
        ticket = await self.get(restaurant_id, id)
        if ticket is None:
            raise NotFoundError(detail="Kitchen ticket not found in this restaurant.")
        return ticket

    async def find_active_for_order(
        self, restaurant_id: uuid.UUID, order_id: uuid.UUID
    ) -> KitchenTicket | None:
        return await self.session.scalar(
            select(KitchenTicket).where(
                KitchenTicket.restaurant_id == restaurant_id,
                KitchenTicket.order_id == order_id,
                KitchenTicket.status.in_(KITCHEN_TICKET_ACTIVE),
            )
        )

    async def list_active_for_branch(
        self, restaurant_id: uuid.UUID, branch_id: uuid.UUID
    ) -> list[KitchenTicket]:
        stmt = (
            select(KitchenTicket)
            .where(
                KitchenTicket.restaurant_id == restaurant_id,
                KitchenTicket.branch_id == branch_id,
                KitchenTicket.status.in_(KITCHEN_TICKET_ACTIVE),
            )
            .options(selectinload(KitchenTicket.order))
            .order_by(KitchenTicket.created_at.asc())
        )
        return list((await self.session.scalars(stmt)).all())


class KitchenStationRepository(TenantScopedRepository[KitchenStation]):
    model = KitchenStation

    async def get_or_404(
        self, restaurant_id: uuid.UUID, id: uuid.UUID
    ) -> KitchenStation:
        station = await self.get(restaurant_id, id)
        if station is None:
            raise NotFoundError(detail="Kitchen station not found in this restaurant.")
        return station

    async def list_for_branch(
        self, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None = None
    ) -> list[KitchenStation]:
        stmt = select(KitchenStation).where(
            KitchenStation.restaurant_id == restaurant_id
        )
        if branch_id is not None:
            stmt = stmt.where(KitchenStation.branch_id == branch_id)
        stmt = stmt.order_by(KitchenStation.name)
        return list((await self.session.scalars(stmt)).all())