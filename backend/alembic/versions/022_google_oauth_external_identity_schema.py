"""Google OAuth External Identity and State Schema

Revision ID: 022_google_oauth_external_identity_schema
Revises: 021_token_revocation_persistence_schema
Create Date: 2026-10-03 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '022_google_oauth_external_identity_schema'
down_revision: Union[str, None] = '021_token_revocation_persistence_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. user_external_identities
    if 'user_external_identities' not in tables:
        op.create_table(
            'user_external_identities',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False),
            sa.Column('provider_subject', sa.String(255), nullable=False),
            sa.Column('provider_email', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('provider', 'provider_subject', name='uq_user_external_identity_provider_sub')
        )
        op.create_index('ix_user_external_identities_user_id', 'user_external_identities', ['user_id'])
        op.create_index('ix_user_external_identities_provider', 'user_external_identities', ['provider'])
        op.create_index('ix_user_external_identities_provider_subject', 'user_external_identities', ['provider_subject'])

    # 2. oauth_states
    if 'oauth_states' not in tables:
        op.create_table(
            'oauth_states',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('state', sa.String(128), unique=True, nullable=False),
            sa.Column('provider', sa.String(50), nullable=False),
            sa.Column('redirect_uri', sa.Text(), nullable=False),
            sa.Column('code_verifier', sa.String(128), nullable=True),
            sa.Column('frontend_redirect_url', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('is_consumed', sa.Boolean(), default=False, nullable=False),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_oauth_states_state', 'oauth_states', ['state'])

    # 3. oauth_exchange_codes
    if 'oauth_exchange_codes' not in tables:
        op.create_table(
            'oauth_exchange_codes',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('code', sa.String(128), unique=True, nullable=False),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('is_consumed', sa.Boolean(), default=False, nullable=False),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_oauth_exchange_codes_code', 'oauth_exchange_codes', ['code'])
        op.create_index('ix_oauth_exchange_codes_user_id', 'oauth_exchange_codes', ['user_id'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'oauth_exchange_codes' in tables:
        op.drop_table('oauth_exchange_codes')
    if 'oauth_states' in tables:
        op.drop_table('oauth_states')
    if 'user_external_identities' in tables:
        op.drop_table('user_external_identities')
