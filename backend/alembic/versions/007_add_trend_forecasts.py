"""Add trend_forecasts table

Revision ID: 007
Revises: 006
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trend_forecasts",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_id",       postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forecast_date",   sa.Date,    nullable=False),
        sa.Column("predicted_count", sa.Float,   nullable=False),
        sa.Column("confidence_low",  sa.Float,   nullable=False),
        sa.Column("confidence_high", sa.Float,   nullable=False),
        sa.Column("model_used",      sa.String(50), nullable=False, server_default="holt_damped"),
        sa.Column("generated_at",    sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_trend_forecasts_entity_date",
        "trend_forecasts",
        ["entity_id", "forecast_date"],
    )
    op.create_index(
        "ix_trend_forecasts_date",
        "trend_forecasts",
        ["forecast_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_trend_forecasts_date",        table_name="trend_forecasts")
    op.drop_index("ix_trend_forecasts_entity_date", table_name="trend_forecasts")
    op.drop_table("trend_forecasts")
