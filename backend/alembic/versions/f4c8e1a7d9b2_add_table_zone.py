"""add tables.zone for the waiter app's hall/room picker

Revision ID: f4c8e1a7d9b2
Revises: e7f3a9c2b6d4
Create Date: 2026-09-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4c8e1a7d9b2'
down_revision: Union[str, None] = 'e7f3a9c2b6d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tables', sa.Column('zone', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('tables', 'zone')
