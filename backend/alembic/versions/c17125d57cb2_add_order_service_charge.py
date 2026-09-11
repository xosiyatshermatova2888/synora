"""add order service_charge

Revision ID: c17125d57cb2
Revises: c450bda51a4f
Create Date: 2026-09-11 23:23:13.510155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c17125d57cb2'
down_revision: Union[str, None] = 'c450bda51a4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default backfills existing rows to 0.00 (required — NOT NULL on
    # a non-empty table); dropped right after so the column matches
    # subtotal/discount/tax, which rely only on the app-level Decimal("0.00")
    # default on INSERT, not a standing DB default.
    op.add_column(
        'orders',
        sa.Column(
            'service_charge',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default='0.00',
        ),
    )
    op.alter_column('orders', 'service_charge', server_default=None)


def downgrade() -> None:
    op.drop_column('orders', 'service_charge')