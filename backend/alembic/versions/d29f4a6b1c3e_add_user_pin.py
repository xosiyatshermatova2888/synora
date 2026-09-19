"""add user pin_hash for waiter PIN login

Revision ID: d29f4a6b1c3e
Revises: c17125d57cb2
Create Date: 2026-09-15 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd29f4a6b1c3e'
down_revision: Union[str, None] = 'c17125d57cb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: most existing users (owners/admins signing in with email)
    # never set one. A non-NULL value both stores the hashed PIN and acts as
    # the "this staff member appears on the waiter kiosk" flag.
    op.add_column('users', sa.Column('pin_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'pin_hash')
