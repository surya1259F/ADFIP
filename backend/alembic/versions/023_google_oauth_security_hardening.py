"""Google OAuth Security Hardening Schema

Revision ID: 023_google_oauth_security_hardening
Revises: 022_google_oauth_external_identity_schema
Create Date: 2026-10-03 19:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '023_google_oauth_security_hardening'
down_revision: Union[str, None] = '022_google_oauth_external_identity_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. Update oauth_states
    if 'oauth_states' in tables:
        state_cols = {c['name'] for c in insp.get_columns('oauth_states')}
        with op.batch_alter_table('oauth_states') as batch_op:
            if 'purpose' not in state_cols:
                batch_op.add_column(sa.Column('purpose', sa.String(20), server_default='LOGIN', nullable=False))
            if 'target_user_id' not in state_cols:
                batch_op.add_column(sa.Column('target_user_id', sa.String(36), nullable=True))
                batch_op.create_foreign_key('fk_oauth_states_target_user_id', 'users', ['target_user_id'], ['id'], ondelete='CASCADE')
                batch_op.create_index('ix_oauth_states_target_user_id', ['target_user_id'])
            if 'nonce' not in state_cols:
                batch_op.add_column(sa.Column('nonce', sa.String(128), nullable=True))
            if 'frontend_origin' not in state_cols:
                batch_op.add_column(sa.Column('frontend_origin', sa.String(255), nullable=True))

    # 2. Update oauth_exchange_codes
    if 'oauth_exchange_codes' in tables:
        code_cols = {c['name'] for c in insp.get_columns('oauth_exchange_codes')}
        with op.batch_alter_table('oauth_exchange_codes') as batch_op:
            batch_op.alter_column('user_id', existing_type=sa.String(36), nullable=True)
            batch_op.alter_column('code', existing_type=sa.String(128), nullable=True)
            if 'code_hash' not in code_cols:
                batch_op.add_column(sa.Column('code_hash', sa.String(64), nullable=True))
                batch_op.create_index('ix_oauth_exchange_codes_code_hash', ['code_hash'], unique=True)
            if 'purpose' not in code_cols:
                batch_op.add_column(sa.Column('purpose', sa.String(20), server_default='LOGIN', nullable=False))
                batch_op.create_index('ix_oauth_exchange_codes_purpose', ['purpose'])
            if 'target_user_id' not in code_cols:
                batch_op.add_column(sa.Column('target_user_id', sa.String(36), nullable=True))
                batch_op.create_foreign_key('fk_oauth_exchange_codes_target_user_id', 'users', ['target_user_id'], ['id'], ondelete='CASCADE')
                batch_op.create_index('ix_oauth_exchange_codes_target_user_id', ['target_user_id'])
            if 'google_sub' not in code_cols:
                batch_op.add_column(sa.Column('google_sub', sa.String(255), nullable=True))
            if 'google_email' not in code_cols:
                batch_op.add_column(sa.Column('google_email', sa.String(255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'oauth_exchange_codes' in tables:
        indexes = {i['name'] for i in insp.get_indexes('oauth_exchange_codes')}
        if 'ix_oauth_exchange_codes_code_hash' in indexes:
            op.drop_index('ix_oauth_exchange_codes_code_hash', table_name='oauth_exchange_codes')
        if 'ix_oauth_exchange_codes_purpose' in indexes:
            op.drop_index('ix_oauth_exchange_codes_purpose', table_name='oauth_exchange_codes')
        if 'ix_oauth_exchange_codes_target_user_id' in indexes:
            op.drop_index('ix_oauth_exchange_codes_target_user_id', table_name='oauth_exchange_codes')

        code_cols = {c['name'] for c in insp.get_columns('oauth_exchange_codes')}
        with op.batch_alter_table('oauth_exchange_codes') as batch_op:
            if 'code_hash' in code_cols:
                batch_op.drop_column('code_hash')
            if 'purpose' in code_cols:
                batch_op.drop_column('purpose')
            if 'target_user_id' in code_cols:
                batch_op.drop_column('target_user_id')
            if 'google_sub' in code_cols:
                batch_op.drop_column('google_sub')
            if 'google_email' in code_cols:
                batch_op.drop_column('google_email')
            batch_op.alter_column('user_id', existing_type=sa.String(36), nullable=False)
            batch_op.alter_column('code', existing_type=sa.String(128), nullable=False)

    if 'oauth_states' in tables:
        indexes = {i['name'] for i in insp.get_indexes('oauth_states')}
        if 'ix_oauth_states_target_user_id' in indexes:
            op.drop_index('ix_oauth_states_target_user_id', table_name='oauth_states')

        state_cols = {c['name'] for c in insp.get_columns('oauth_states')}
        with op.batch_alter_table('oauth_states') as batch_op:
            if 'purpose' in state_cols:
                batch_op.drop_column('purpose')
            if 'target_user_id' in state_cols:
                batch_op.drop_column('target_user_id')
            if 'nonce' in state_cols:
                batch_op.drop_column('nonce')
            if 'frontend_origin' in state_cols:
                batch_op.drop_column('frontend_origin')
