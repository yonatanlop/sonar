"""Enriquecimiento de datos de Twitter: location_text en perfiles y conversation_id en menciones

Revision ID: 015
Revises: 014
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    # Ubicación texto del usuario (campo libre de Twitter: "Bogotá, Colombia")
    op.add_column(
        "account_profiles",
        sa.Column("location_text", sa.String(200), nullable=True),
    )

    # ID de conversación/hilo del tweet (permite agrupar tweets del mismo thread)
    op.add_column(
        "mentions",
        sa.Column("conversation_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_mentions_conversation_id", "mentions", ["conversation_id"])


def downgrade():
    op.drop_index("ix_mentions_conversation_id", table_name="mentions")
    op.drop_column("mentions", "conversation_id")
    op.drop_column("account_profiles", "location_text")
