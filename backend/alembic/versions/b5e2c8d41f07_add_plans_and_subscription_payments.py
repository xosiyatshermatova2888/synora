"""add plans, subscription state and subscription payments

Revision ID: b5e2c8d41f07
Revises: a21e6dcda6da
Create Date: 2026-10-12 10:00:00.000000

Existing restaurants are backfilled to BUSINESS / ACTIVE with no expiry (the
server defaults below do that for every pre-existing row); only restaurants
registered after this migration start on the 14-day Pro trial.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5e2c8d41f07'
down_revision: Union[str, None] = 'a21e6dcda6da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('restaurants', sa.Column('plan', sa.String(length=20), server_default='BUSINESS', nullable=False))
    op.add_column('restaurants', sa.Column('subscription_status', sa.String(length=10), server_default='ACTIVE', nullable=False))
    op.add_column('restaurants', sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('restaurants', sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('restaurants', sa.Column('billing_cycle', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('is_platform_admin', sa.Boolean(), server_default='false', nullable=False))

    op.create_table(
        'subscription_payments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('restaurant_id', sa.UUID(), nullable=False),
        sa.Column('plan', sa.String(length=20), nullable=False),
        sa.Column('billing_cycle', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('receipt_url', sa.String(length=500), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('requested_by_user_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_by_user_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_subscription_payments_restaurant_id'), 'subscription_payments', ['restaurant_id'])
    op.create_index(op.f('ix_subscription_payments_status'), 'subscription_payments', ['status'])
    op.create_index(op.f('ix_subscription_payments_created_at'), 'subscription_payments', ['created_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_subscription_payments_created_at'), table_name='subscription_payments')
    op.drop_index(op.f('ix_subscription_payments_status'), table_name='subscription_payments')
    op.drop_index(op.f('ix_subscription_payments_restaurant_id'), table_name='subscription_payments')
    op.drop_table('subscription_payments')
    op.drop_column('users', 'is_platform_admin')
    op.drop_column('restaurants', 'billing_cycle')
    op.drop_column('restaurants', 'current_period_end')
    op.drop_column('restaurants', 'trial_ends_at')
    op.drop_column('restaurants', 'subscription_status')
    op.drop_column('restaurants', 'plan')
