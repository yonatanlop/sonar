"""add keyword_secondary column to keywords table

Revision ID: 023
Revises: 022
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op

revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'keywords',
        sa.Column('keyword_secondary', sa.String(200), nullable=True),
    )


def downgrade():
    op.drop_column('keywords', 'keyword_secondary')
