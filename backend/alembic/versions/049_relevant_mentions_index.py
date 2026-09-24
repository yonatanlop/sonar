"""Índice parcial de menciones relevantes para el dashboard

El dashboard ahora cuenta solo menciones con is_relevant = true. Un índice parcial
(collected_at, sentiment_label) WHERE is_relevant mantiene el index-only scan de las
agregaciones por rango de fecha (ver 043), ahora con el filtro de relevancia.

Revision ID: 049
Revises: 048
Create Date: 2026-09-24
"""
from alembic import op

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mentions_collected_sentiment_rel "
        "ON mentions (collected_at, sentiment_label) WHERE is_relevant"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_mentions_collected_sentiment_rel")
