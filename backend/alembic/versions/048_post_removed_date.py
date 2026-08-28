"""Seguimiento a caso: fecha de eliminación de la publicación

Agrega case_records.post_removed_date para poder listar las publicaciones
cerradas en un mes en el reporte.

Revision ID: 048
Revises: 047
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("case_records", sa.Column("post_removed_date", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("case_records", "post_removed_date")
