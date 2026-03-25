"""Add daily_summaries table

Revision ID: 004
Revises: 003
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(80), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entity_id", "summary_date", name="uq_entity_summary_date"),
    )
    op.create_index("ix_daily_summaries_entity_date",
                    "daily_summaries", ["entity_id", "summary_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_summaries_entity_date", table_name="daily_summaries")
    op.drop_table("daily_summaries")
