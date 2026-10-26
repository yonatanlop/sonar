"""Permitir borrar menciones viejas que ya tienen keywords asociadas

- mention_keywords.mention_id no tenía ON DELETE CASCADE (igual que le pasaba
  a keyword_id antes de la migración 052). La tarea diaria cleanup_old_mentions
  borra menciones con mas de 12 meses en un DELETE en bloque; como casi toda
  mencion tiene filas en mention_keywords, Postgres rechazaba el DELETE completo
  por violacion de FK y la tarea quedaba sin borrar nada, silenciosamente
  (el error se atrapa y se loguea, pero nunca se relanza).
- Ahora, al borrar una mencion, se borra en cascada su fila de asociacion en
  mention_keywords (el vinculo "esta mencion la disparo esta keyword").

Revision ID: 055
Revises: 054
Create Date: 2026-10-26
"""
from alembic import op

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("mention_keywords_mention_id_fkey", "mention_keywords", type_="foreignkey")
    op.create_foreign_key(
        "mention_keywords_mention_id_fkey", "mention_keywords", "mentions",
        ["mention_id"], ["id"], ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("mention_keywords_mention_id_fkey", "mention_keywords", type_="foreignkey")
    op.create_foreign_key(
        "mention_keywords_mention_id_fkey", "mention_keywords", "mentions",
        ["mention_id"], ["id"],
    )
