"""Eventos del día por entidad (para el informe de actividad de menciones)

Revision ID: 053
Revises: 052
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "entity_day_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_entity_day_events_entity_date", "entity_day_events", ["entity_id", "event_date"])


def downgrade():
    op.drop_index("ix_entity_day_events_entity_date", table_name="entity_day_events")
    op.drop_table("entity_day_events")
