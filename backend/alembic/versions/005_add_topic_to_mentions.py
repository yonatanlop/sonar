"""Add topic_id and topic_label to mentions

Revision ID: 005
Revises: 004
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mentions", sa.Column("topic_id",    sa.Integer(),     nullable=True))
    op.add_column("mentions", sa.Column("topic_label", sa.String(120),   nullable=True))
    op.create_index("ix_mentions_topic", "mentions", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_mentions_topic", table_name="mentions")
    op.drop_column("mentions", "topic_label")
    op.drop_column("mentions", "topic_id")
