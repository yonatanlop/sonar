"""Índice para la lista global de menciones (sin filtro de entidad)

GET /mentions sin entity_id hace WHERE is_relevant = true ORDER BY
coalesce(published_at, collected_at) DESC sobre toda la tabla mentions
(885.000+ filas y creciendo) sin ningún índice que lo cubra: cada apertura de
"Menciones" sin filtrar hace un seq scan + sort completo, que en esta VM de
1GB tarda varios segundos y mantiene ocupada una conexión del pool. Con el
scraping escribiendo todo el tiempo, eso agota el pool (5 + 10 overflow) y
cualquier otra petición (p. ej. agregar una keyword) se queda esperando 30s
y termina en 500 "QueuePool limit... connection timed out".

Revision ID: 054
Revises: 053
Create Date: 2026-10-09
"""
from alembic import op

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mentions_relevant_pubdate
        ON mentions (COALESCE(published_at, collected_at) DESC)
        WHERE is_relevant = true
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_mentions_relevant_pubdate")
