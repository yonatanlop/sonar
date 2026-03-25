"""add is_duplicate to mentions

Revision ID: 011
Revises: 010
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "mentions",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_mentions_is_duplicate", "mentions", ["is_duplicate"])


def downgrade():
    op.drop_index("ix_mentions_is_duplicate", table_name="mentions")
    op.drop_column("mentions", "is_duplicate")
