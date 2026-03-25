"""Add vector embeddings to mentions (pgvector)

Revision ID: 010
Revises: 009
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Habilitar extensión pgvector (requiere pgvector/pgvector:pg15 en docker-compose)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Columna de embedding (384 dims — paraphrase-multilingual-MiniLM-L12-v2)
    op.execute("ALTER TABLE mentions ADD COLUMN IF NOT EXISTS embedding vector(384)")

    # Índice IVFFlat para búsqueda aproximada por similitud coseno.
    # Nota: solo se puede crear cuando la tabla tiene ≥ 1 fila con embedding no nulo.
    # Si el índice falla en la migración, créalo manualmente después de cargar datos:
    #   CREATE INDEX ix_mentions_embedding ON mentions
    #   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    try:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_mentions_embedding ON mentions "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )
    except Exception:
        pass   # Se crea manualmente cuando haya datos suficientes


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mentions_embedding")
    op.execute("ALTER TABLE mentions DROP COLUMN IF EXISTS embedding")
