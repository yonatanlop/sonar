"""Permitir borrar una keyword que ya tiene menciones asociadas

- mention_keywords.keyword_id no tenía ON DELETE CASCADE: borrar una keyword con
  menciones ya disparadas por ella violaba la FK (ForeignKeyViolation) y el
  endpoint DELETE /entities/{id}/keywords/{keyword_id} respondía 500.
- Ahora, al borrar la keyword, solo se borra su fila de asociación en
  mention_keywords (el vínculo "esta mención la disparó esta keyword").
  Las menciones en sí (mentions.id) no se tocan ni se borran.

Revision ID: 052
Revises: 051
Create Date: 2026-09-30
"""
from alembic import op

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("mention_keywords_keyword_id_fkey", "mention_keywords", type_="foreignkey")
    op.create_foreign_key(
        "mention_keywords_keyword_id_fkey", "mention_keywords", "keywords",
        ["keyword_id"], ["id"], ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("mention_keywords_keyword_id_fkey", "mention_keywords", type_="foreignkey")
    op.create_foreign_key(
        "mention_keywords_keyword_id_fkey", "mention_keywords", "keywords",
        ["keyword_id"], ["id"],
    )
