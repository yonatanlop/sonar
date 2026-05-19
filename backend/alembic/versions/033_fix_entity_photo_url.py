"""fix entity photo_url column from VARCHAR(500) to TEXT

Revision ID: 033
Revises: 032
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column(
        'entities', 'photo_url',
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        'entities', 'photo_url',
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
    )
