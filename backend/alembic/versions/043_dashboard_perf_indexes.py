"""Índices para acelerar el dashboard: rango por collected_at

El dashboard filtra masivamente por `collected_at` SOLO (sin entity_id), pero el
único índice que lo tocaba era el compuesto (entity_id, collected_at): como
collected_at es la 2ª columna, Postgres no podía hacer un seek por rango y
escaneaba el índice completo (~2.7s por consulta sobre 739K filas). El timeline
repetía eso 14 veces.

Este índice (collected_at, sentiment_label) permite un seek por rango de fecha y
además cubre las consultas que filtran/agrupan por sentimiento en el mismo período.

Revision ID: 043
Revises: 042
Create Date: 2026-08-23
"""
from alembic import op

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade():
    # IF NOT EXISTS por si el índice ya se creó a mano en algún entorno.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mentions_collected_sentiment "
        "ON mentions (collected_at, sentiment_label)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_mentions_collected_sentiment")
