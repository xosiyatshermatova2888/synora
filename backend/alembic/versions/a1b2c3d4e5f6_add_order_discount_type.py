"""add orders.discount_type for percentage-vs-fixed discounts

Revision ID: a1b2c3d4e5f6
Revises: f4c8e1a7d9b2
Create Date: 2026-09-20 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f4c8e1a7d9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'orders',
        sa.Column('discount_type', sa.String(length=10), nullable=False, server_default='FIXED'),
    )


def downgrade() -> None:
    op.drop_column('orders', 'discount_type')
