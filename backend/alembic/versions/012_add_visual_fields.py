"""Módulo 7: campos de reconocimiento visual en mentions

Revision ID: 012
Revises: 011
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # JSON array de URLs de imágenes adjuntas al post (ej: imágenes de tweets)
    op.add_column("mentions", sa.Column(
        "media_urls", sa.Text(), nullable=True,
        comment="JSON array de URLs de imágenes adjuntas al post",
    ))

    # NULL = no analizado, True = match encontrado, False = analizado sin match
    op.add_column("mentions", sa.Column(
        "visual_match", sa.Boolean(), nullable=True,
        comment="True si se detectó visualmente a una persona monitorizada",
    ))

    # JSON array de nombres detectados, ej: ["Ana Paola Agudelo"]
    op.add_column("mentions", sa.Column(
        "visual_match_names", sa.Text(), nullable=True,
        comment="JSON array con los nombres de personas detectadas",
    ))

    # Índice para filtrar rápido por menciones con coincidencia visual
    op.create_index("ix_mentions_visual_match", "mentions", ["visual_match"])


def downgrade():
    op.drop_index("ix_mentions_visual_match", table_name="mentions")
    op.drop_column("mentions", "visual_match_names")
    op.drop_column("mentions", "visual_match")
    op.drop_column("mentions", "media_urls")
