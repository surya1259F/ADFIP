"""Add intent column to oauth_states table

Revision ID: 025_add_oauth_intent_to_state
Revises: 024_add_user_avatar_url
Create Date: 2026-10-06 18:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '025_add_oauth_intent_to_state'
down_revision: Union[str, None] = '024_add_user_avatar_url'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'oauth_states' in tables:
        state_cols = {c['name'] for c in insp.get_columns('oauth_states')}
        with op.batch_alter_table('oauth_states') as batch_op:
            if 'intent' not in state_cols:
                batch_op.add_column(
                    sa.Column('intent', sa.String(length=20), server_default='SIGN_IN', nullable=False)
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'oauth_states' in tables:
        state_cols = {c['name'] for c in insp.get_columns('oauth_states')}
        with op.batch_alter_table('oauth_states') as batch_op:
            if 'intent' in state_cols:
                batch_op.drop_column('intent')

