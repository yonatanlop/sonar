"""add twitter keyword search tables

Revision ID: 029
Revises: 028
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade():
    # Tabla de configuración global (una sola fila activa)
    op.create_table(
        'twitter_keyword_config',
        sa.Column('id',              sa.Integer(),               nullable=False, autoincrement=True),
        sa.Column('is_active',       sa.Boolean(),               nullable=False, server_default='false'),
        sa.Column('activated_at',    sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped_at',      sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at',     sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_by_id', UUID(as_uuid=True),         nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['activated_by_id'], ['users.id'], ondelete='SET NULL'),
    )
    # Insertar la fila de configuración inicial
    op.execute("INSERT INTO twitter_keyword_config (is_active) VALUES (false)")

    # Tabla de términos de búsqueda (keywords y hashtags)
    op.create_table(
        'twitter_keyword_terms',
        sa.Column('id',            sa.Integer(),               nullable=False, autoincrement=True),
        sa.Column('term',          sa.String(200),             nullable=False),
        sa.Column('term_type',     sa.String(10),              nullable=False),  # 'keyword' | 'hashtag'
        sa.Column('is_active',     sa.Boolean(),               nullable=False, server_default='true'),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('created_by_id', UUID(as_uuid=True),         nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_twitter_keyword_terms_active', 'twitter_keyword_terms', ['is_active'])


def downgrade():
    op.drop_index('ix_twitter_keyword_terms_active', table_name='twitter_keyword_terms')
    op.drop_table('twitter_keyword_terms')
    op.drop_table('twitter_keyword_config')
