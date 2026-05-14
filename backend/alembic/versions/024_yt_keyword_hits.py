"""add yt_keyword_hits table

Revision ID: 024
Revises: 023
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op

revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'yt_keyword_hits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('hash', sa.String(64), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('keyword_id', sa.Integer(), nullable=True),
        sa.Column('keyword', sa.String(200), nullable=False),
        sa.Column('yt_media_video_id', sa.String(50), nullable=False),
        sa.Column('inicio', sa.String(20), nullable=True),
        sa.Column('texto', sa.Text(), nullable=True),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('query_date', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['channel_id'], ['youtube_channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['keyword_id'], ['youtube_channel_keywords.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hash', name='uq_yt_keyword_hit_hash'),
    )
    op.create_index('ix_yt_keyword_hits_hash',       'yt_keyword_hits', ['hash'])
    op.create_index('ix_yt_keyword_hits_channel_id', 'yt_keyword_hits', ['channel_id'])
    op.create_index('ix_yt_keyword_hits_keyword_id', 'yt_keyword_hits', ['keyword_id'])


def downgrade():
    op.drop_index('ix_yt_keyword_hits_keyword_id', table_name='yt_keyword_hits')
    op.drop_index('ix_yt_keyword_hits_channel_id', table_name='yt_keyword_hits')
    op.drop_index('ix_yt_keyword_hits_hash',       table_name='yt_keyword_hits')
    op.drop_table('yt_keyword_hits')
