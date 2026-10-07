"""Add challenge_category to investigator_reviews table

Revision ID: 026_add_challenge_category_to_investigator_reviews
Revises: 025_add_oauth_intent_to_state
Create Date: 2026-10-07 08:15:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '026_add_challenge_category_to_investigator_reviews'
down_revision: Union[str, None] = '025_add_oauth_intent_to_state'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'investigator_reviews' in tables:
        cols = {c['name'] for c in insp.get_columns('investigator_reviews')}
        with op.batch_alter_table('investigator_reviews') as batch_op:
            if 'challenge_category' not in cols:
                batch_op.add_column(
                    sa.Column('challenge_category', sa.String(), nullable=True)
                )
                batch_op.create_index('ix_investigator_reviews_challenge_category', ['challenge_category'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'investigator_reviews' in tables:
        cols = {c['name'] for c in insp.get_columns('investigator_reviews')}
        with op.batch_alter_table('investigator_reviews') as batch_op:
            if 'challenge_category' in cols:
                batch_op.drop_index('ix_investigator_reviews_challenge_category')
                batch_op.drop_column('challenge_category')

