"""Add avatar_url column to users table

Revision ID: 024_add_user_avatar_url
Revises: 023_google_oauth_security_hardening
Create Date: 2026-10-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = '024_add_user_avatar_url'
down_revision: str = '023_google_oauth_security_hardening'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('avatar_url', sa.String(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('avatar_url')
