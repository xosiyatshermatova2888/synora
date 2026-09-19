"""rename users.email to username, drop password reset tokens

Revision ID: e7f3a9c2b6d4
Revises: d29f4a6b1c3e
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7f3a9c2b6d4'
down_revision: Union[str, None] = 'd29f4a6b1c3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Login is now a free-form username, not an email address — existing
    # values carry over unchanged (an old "owner@x.com" simply becomes that
    # user's username going forward).
    op.alter_column('users', 'email', new_column_name='username')
    op.drop_index('ix_users_email', table_name='users')
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Self-service password reset (email-based) is removed in favor of an
    # admin resetting a staff member's password directly.
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_token_hash'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')


def downgrade() -> None:
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.alter_column('users', 'username', new_column_name='email')
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
