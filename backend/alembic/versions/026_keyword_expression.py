"""add keyword_expression to keywords

Revision ID: 026
Revises: 025
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op

revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'keywords',
        sa.Column('keyword_expression', sa.Text, nullable=True),
    )


def downgrade():
    op.drop_column('keywords', 'keyword_expression')
