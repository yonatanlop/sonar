"""youtube_channels and youtube_channel_keywords tables

Revision ID: 019
Revises: 018
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'youtube_channels',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('handle', sa.String(100), nullable=False),
        sa.Column('channel_id', sa.String(50), nullable=False),
        sa.Column('channel_name', sa.String(200), nullable=False),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('entity_id', PG_UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', PG_UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('handle', name='uq_yt_channel_handle'),
        sa.UniqueConstraint('channel_id', name='uq_yt_channel_id'),
    )
    op.create_table(
        'youtube_channel_keywords',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('keyword', sa.String(200), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['channel_id'], ['youtube_channels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('youtube_channel_keywords')
    op.drop_table('youtube_channels')
