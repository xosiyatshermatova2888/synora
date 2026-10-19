"""printer auto_print_orders (full copy of new orders on the cashier printer)

Revision ID: d4a8e61b2c93
Revises: c7d1a93e5b20
Create Date: 2026-10-18 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4a8e61b2c93'
down_revision: Union[str, None] = 'c7d1a93e5b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('printers', sa.Column('auto_print_orders', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('printers', 'auto_print_orders')
