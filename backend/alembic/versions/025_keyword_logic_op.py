"""add logic_op to keywords

Revision ID: 025
Revises: 024
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op

revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'keywords',
        sa.Column('logic_op', sa.String(3), nullable=False, server_default='AND'),
    )


def downgrade():
    op.drop_column('keywords', 'logic_op')
