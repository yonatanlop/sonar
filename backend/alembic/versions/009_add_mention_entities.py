"""Add mention_entities table for NER co-occurrence

Revision ID: 009
Revises: 008
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mention_entities",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mention_id",  postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mentions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(10),  nullable=False),   # PER | ORG | LOC
        sa.Column("entity_text", sa.String(200), nullable=False),
    )
    op.create_index("ix_mention_entities_mention",   "mention_entities", ["mention_id"])
    op.create_index("ix_mention_entities_type_text", "mention_entities", ["entity_type", "entity_text"])


def downgrade() -> None:
    op.drop_index("ix_mention_entities_type_text", table_name="mention_entities")
    op.drop_index("ix_mention_entities_mention",   table_name="mention_entities")
    op.drop_table("mention_entities")
