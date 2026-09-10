"""Payment + cash shift repositories (tenant-scoped)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.models.payment import CashShift, Payment
from app.repositories.base import TenantScopedRepository
from app.utils.errors import NotFoundError


class PaymentRepository(TenantScopedRepository[Payment]):
    model = Payment

    async def list_for_order(self, restaurant_id: uuid.UUID, order_id: uuid.UUID) -> list[Payment]:
        stmt = (
            select(self.model)
            .where(
                self.model.restaurant_id == restaurant_id,
                self.model.order_id == order_id,
            )
            .order_by(self.model.created_at)
        )
        return list((await self.session.scalars(stmt)).all())

    async def total_for_order(self, restaurant_id: uuid.UUID, order_id: uuid.UUID) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(self.model.amount), Decimal("0.00")))
            .where(
                self.model.restaurant_id == restaurant_id,
                self.model.order_id == order_id,
                self.model.status == "PAID",
            )
        )
        return await self.session.scalar(stmt)


class CashShiftRepository(TenantScopedRepository[CashShift]):
    model = CashShift

    async def get_or_404(self, restaurant_id: uuid.UUID, id: uuid.UUID) -> CashShift:
        shift = await self.get(restaurant_id, id)
        if shift is None:
            raise NotFoundError(detail="Cash shift not found in this restaurant.")
        return shift

    async def open_shift_for_user(
        self, restaurant_id: uuid.UUID, branch_id: uuid.UUID, user_id: uuid.UUID
    ) -> CashShift | None:
        stmt = (
            select(self.model)
            .where(
                self.model.restaurant_id == restaurant_id,
                self.model.branch_id == branch_id,
                self.model.cashier_user_id == user_id,
                self.model.status == "OPEN",
                self.model.is_active.is_(True),
            )
            .order_by(self.model.opened_at.desc())
        )
        return await self.session.scalar(stmt)

    async def cash_collected(
        self, restaurant_id: uuid.UUID, branch_id: uuid.UUID, since
    ) -> Decimal:
        """Sum of successfully PAID cash payments in this branch after `since`.

        Used to compute a cash shift's expected closing balance (Section 15).
        """
        from decimal import Decimal

        from app.models.order import Order

        stmt = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .where(
                Payment.restaurant_id == restaurant_id,
                Payment.method == "CASH",
                Payment.status == "PAID",
                Payment.created_at >= since,
                Payment.order_id.in_(
                    select(Order.id).where(
                        Order.restaurant_id == restaurant_id,
                        Order.branch_id == branch_id,
                    )
                ),
            )
        )
        return await self.session.scalar(stmt)