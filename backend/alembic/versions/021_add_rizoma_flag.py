"""add is_rizoma flag to twitter_feeds and youtube_channels

Revision ID: 021
Revises: 020
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'twitter_feeds',
        sa.Column('is_rizoma', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'youtube_channels',
        sa.Column('is_rizoma', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade():
    op.drop_column('twitter_feeds', 'is_rizoma')
    op.drop_column('youtube_channels', 'is_rizoma')
