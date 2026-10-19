"""add print agent (printer mode, queued job payload, agent credentials)

Revision ID: c7d1a93e5b20
Revises: b5e2c8d41f07
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d1a93e5b20'
down_revision: Union[str, None] = 'b5e2c8d41f07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('printers', sa.Column('mode', sa.String(length=10), server_default='DIRECT', nullable=False))
    op.add_column('print_jobs', sa.Column('payload', sa.LargeBinary(), nullable=True))
    op.add_column('print_jobs', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'print_agents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('restaurant_id', sa.UUID(), nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('branch_id'),
    )
    op.create_index(op.f('ix_print_agents_restaurant_id'), 'print_agents', ['restaurant_id'])
    op.create_index(op.f('ix_print_agents_token_hash'), 'print_agents', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_print_agents_token_hash'), table_name='print_agents')
    op.drop_index(op.f('ix_print_agents_restaurant_id'), table_name='print_agents')
    op.drop_table('print_agents')
    op.drop_column('print_jobs', 'claimed_at')
    op.drop_column('print_jobs', 'payload')
    op.drop_column('printers', 'mode')
