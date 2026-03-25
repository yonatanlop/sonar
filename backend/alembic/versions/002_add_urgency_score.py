"""Add urgency_score to mentions

Revision ID: 002
Revises: 001
Create Date: 2026-03-25

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mentions",
        sa.Column(
            "urgency_score",
            sa.Numeric(5, 1),   # rango 0.0 – 100.0
            server_default="0",
            nullable=False,
        ),
    )
    # Índice para filtrar por urgencia mínima eficientemente
    op.create_index("ix_mentions_urgency", "mentions", ["urgency_score"])


def downgrade() -> None:
    op.drop_index("ix_mentions_urgency", table_name="mentions")
    op.drop_column("mentions", "urgency_score")
