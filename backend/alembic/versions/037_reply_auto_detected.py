"""add auto_detected and external_reply_id to mention_replies

Revision ID: 037
Revises: 036
Create Date: 2026-05-22
"""
import sqlalchemy as sa
from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade():
    # Campo para marcar respuestas detectadas automáticamente por el scraper
    op.add_column("mention_replies",
        sa.Column("auto_detected", sa.Boolean(), server_default="false", nullable=False))

    # ID del tweet de respuesta — permite deduplicar en runs sucesivos
    op.add_column("mention_replies",
        sa.Column("external_reply_id", sa.String(50), nullable=True))
    op.create_index("ix_mention_replies_ext_reply_id", "mention_replies", ["external_reply_id"])

    # logged_by pasa a nullable: las detecciones automáticas no tienen usuario
    op.alter_column("mention_replies", "logged_by", nullable=True)


def downgrade():
    op.alter_column("mention_replies", "logged_by", nullable=False)
    op.drop_index("ix_mention_replies_ext_reply_id", table_name="mention_replies")
    op.drop_column("mention_replies", "external_reply_id")
    op.drop_column("mention_replies", "auto_detected")
